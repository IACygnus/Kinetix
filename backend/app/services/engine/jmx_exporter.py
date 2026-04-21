# backend/app/services/engine/jmx_exporter.py
"""
JMX Exporter — Exporta el Script Model interno al formato .jmx de JMeter.

IMPORTANTE: Este modulo es SOLO para exportacion. El motor de ejecucion
de SQA Kinetix Pro NO usa JMX para ejecutar pruebas. El JMX se genera
unicamente para que el cliente pueda abrir el script en su JMeter local
si asi lo desea.

El .jmx generado es XML valido compatible con JMeter 5.5+.
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Dict, Any, List, Optional
from datetime import datetime


class JMXExporter:
    """
    Convierte el Script Model interno (JSON) al formato XML .jmx de JMeter.

    Genera un Test Plan completo con:
    - ThreadGroup con la configuracion del escenario (si se provee)
    - HTTPSamplerProxy por cada request
    - RegexExtractor por cada extractor definido
    - HeaderManager con los headers del request
    - CSVDataSet por cada DataFile asignado
    - ResponseAssertion por cada assertion definida
    """

    def export(self, script_model: Dict[str, Any], scenario_config: Optional[Dict[str, Any]] = None,
               script_name: str = "SQA Kinetix Pro Test") -> str:
        """
        Exportar Script Model a XML JMX.

        Args:
            script_model: El JSON interno del ScriptDesign
            scenario_config: Opcional. Si se provee, incluye ThreadGroup configurado.
                             Si no, usa valores por defecto (1 usuario, 1 iteracion).
            script_name: Nombre del Test Plan

        Returns:
            String XML del .jmx completo
        """
        # Elemento raiz del JMX
        root = ET.Element("jmeterTestPlan", version="1.2", properties="5.0", jmeter="5.6.3")
        hash_tree_root = ET.SubElement(root, "hashTree")

        # Test Plan
        test_plan = ET.SubElement(hash_tree_root, "TestPlan",
            guiclass="TestPlanGui", testclass="TestPlan",
            testname=script_name, enabled="true")
        ET.SubElement(test_plan, "stringProp", name="TestPlan.comments").text = \
            f"Generado por SQA Kinetix Pro — {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        ET.SubElement(test_plan, "boolProp", name="TestPlan.functional_mode").text = "false"
        ET.SubElement(test_plan, "boolProp", name="TestPlan.serialize_threadgroups").text = "false"

        hash_tree_plan = ET.SubElement(hash_tree_root, "hashTree")

        # Thread Group
        tg_config = scenario_config or {}
        self._add_thread_group(hash_tree_plan, tg_config)
        hash_tree_tg = ET.SubElement(hash_tree_plan, "hashTree")

        # CSV Data Sets (uno por cada data file)
        for data_file in script_model.get("data_files", []):
            self._add_csv_dataset(hash_tree_tg, data_file)

        # HTTP Samplers (uno por cada request)
        requests = script_model.get("requests", [])
        for req in requests:
            self._add_http_sampler(hash_tree_tg, req)

        # Convertir a string XML formateado
        xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
        # Pretty print
        dom = minidom.parseString(xml_str)
        pretty = dom.toprettyxml(indent="  ", encoding=None)
        # Remover la linea <?xml version="1.0" ?> que agrega minidom
        lines = pretty.split("\n")
        if lines[0].startswith("<?xml"):
            lines = lines[1:]
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + "\n".join(lines)

    def _add_thread_group(self, parent: ET.Element, config: Dict[str, Any]) -> None:
        """Agregar ThreadGroup al Test Plan."""
        initial_users = config.get("initial_users", 1)
        max_users = config.get("max_users", initial_users)
        ramp_up = config.get("step_duration_sec", 1)
        duration = config.get("total_duration_sec", 0)

        tg = ET.SubElement(parent, "ThreadGroup",
            guiclass="ThreadGroupGui", testclass="ThreadGroup",
            testname="Thread Group", enabled="true")

        ET.SubElement(tg, "stringProp", name="ThreadGroup.on_sample_error").text = "continue"

        loop_ctrl = ET.SubElement(tg, "elementProp", name="ThreadGroup.main_controller",
            elementType="LoopController", guiclass="LoopControlPanel", testclass="LoopController",
            testname="Loop Controller", enabled="true")
        ET.SubElement(loop_ctrl, "boolProp", name="LoopController.continue_forever").text = \
            "true" if duration > 0 else "false"
        ET.SubElement(loop_ctrl, "stringProp", name="LoopController.loops").text = \
            "-1" if duration > 0 else "1"

        ET.SubElement(tg, "stringProp", name="ThreadGroup.num_threads").text = str(max_users)
        ET.SubElement(tg, "stringProp", name="ThreadGroup.ramp_time").text = str(ramp_up)
        ET.SubElement(tg, "boolProp", name="ThreadGroup.scheduler").text = "true" if duration > 0 else "false"
        ET.SubElement(tg, "stringProp", name="ThreadGroup.duration").text = str(duration)
        ET.SubElement(tg, "stringProp", name="ThreadGroup.delay").text = "0"

    def _add_http_sampler(self, parent: ET.Element, req: Dict[str, Any]) -> None:
        """Agregar HTTPSamplerProxy al hashTree."""
        from urllib.parse import urlparse
        parsed = urlparse(req.get("url", "http://example.com"))

        protocol = parsed.scheme or "http"
        domain = parsed.netloc.split(":")[0] if parsed.netloc else "example.com"
        port = parsed.port or ("443" if protocol == "https" else "80")
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        sampler = ET.SubElement(parent, "HTTPSamplerProxy",
            guiclass="HttpTestSampleGui", testclass="HTTPSamplerProxy",
            testname=req.get("name", "Request"), enabled="true")

        ET.SubElement(sampler, "stringProp", name="HTTPSampler.domain").text = domain
        ET.SubElement(sampler, "stringProp", name="HTTPSampler.port").text = str(port)
        ET.SubElement(sampler, "stringProp", name="HTTPSampler.protocol").text = protocol
        ET.SubElement(sampler, "stringProp", name="HTTPSampler.path").text = path
        ET.SubElement(sampler, "stringProp", name="HTTPSampler.method").text = req.get("method", "GET").upper()
        ET.SubElement(sampler, "boolProp", name="HTTPSampler.follow_redirects").text = "true"
        ET.SubElement(sampler, "boolProp", name="HTTPSampler.auto_redirects").text = "false"
        ET.SubElement(sampler, "boolProp", name="HTTPSampler.use_keepalive").text = "true"

        # Body
        body = req.get("body", "")
        if body and req.get("method", "GET").upper() not in ("GET", "HEAD"):
            ET.SubElement(sampler, "boolProp", name="HTTPSampler.postBodyRaw").text = "true"
            args = ET.SubElement(sampler, "elementProp", name="HTTPsampler.Arguments",
                elementType="Arguments")
            coll = ET.SubElement(args, "collectionProp", name="Arguments.arguments")
            arg = ET.SubElement(coll, "elementProp", name="", elementType="HTTPArgument")
            ET.SubElement(arg, "boolProp", name="HTTPArgument.always_encode").text = "false"
            ET.SubElement(arg, "stringProp", name="Argument.value").text = body
            ET.SubElement(arg, "stringProp", name="Argument.metadata").text = "="

        hash_tree_sampler = ET.SubElement(parent, "hashTree")

        # Headers
        headers = req.get("headers", {})
        if headers:
            hm = ET.SubElement(hash_tree_sampler, "HeaderManager",
                guiclass="HeaderPanel", testclass="HeaderManager",
                testname="HTTP Header Manager", enabled="true")
            coll = ET.SubElement(hm, "collectionProp", name="HeaderManager.headers")
            for k, v in headers.items():
                el = ET.SubElement(coll, "elementProp", name="", elementType="Header")
                ET.SubElement(el, "stringProp", name="Header.name").text = k
                ET.SubElement(el, "stringProp", name="Header.value").text = str(v)
            ET.SubElement(hash_tree_sampler, "hashTree")

        # Extractors (RegexExtractor)
        for extractor in req.get("extractors", []):
            self._add_regex_extractor(hash_tree_sampler, extractor)

        # Assertions
        for assertion in req.get("assertions", []):
            self._add_assertion(hash_tree_sampler, assertion)

        # Think time (Timer)
        think_time = req.get("think_time_ms", 0)
        if think_time > 0:
            timer = ET.SubElement(hash_tree_sampler, "ConstantTimer",
                guiclass="ConstantTimerGui", testclass="ConstantTimer",
                testname="Think Time", enabled="true")
            ET.SubElement(timer, "stringProp", name="ConstantTimer.delay").text = str(think_time)
            ET.SubElement(hash_tree_sampler, "hashTree")

    def _add_regex_extractor(self, parent: ET.Element, extractor: Dict[str, Any]) -> None:
        """Agregar RegexExtractor al hashTree del sampler."""
        ext = ET.SubElement(parent, "RegexExtractor",
            guiclass="RegexExtractorGui", testclass="RegexExtractor",
            testname=f"Extract {extractor.get('variable_name', 'var')}", enabled="true")

        # Field to check: body=2, headers=3, URL=4, response code=5
        extract_from = extractor.get("extract_from", "body")
        field_val = "2" if extract_from == "body" else "3"
        ET.SubElement(ext, "stringProp", name="RegexExtractor.useHeaders").text = field_val
        ET.SubElement(ext, "stringProp", name="RegexExtractor.refname").text = extractor.get("variable_name", "var")
        ET.SubElement(ext, "stringProp", name="RegexExtractor.regex").text = extractor.get("regex", "")
        ET.SubElement(ext, "stringProp", name="RegexExtractor.template").text = "$1$"
        ET.SubElement(ext, "stringProp", name="RegexExtractor.default").text = extractor.get("default_value", "")
        ET.SubElement(ext, "stringProp", name="RegexExtractor.match_no").text = str(extractor.get("match_no", 1))
        ET.SubElement(parent, "hashTree")

    def _add_assertion(self, parent: ET.Element, assertion: Dict[str, Any]) -> None:
        """Agregar ResponseAssertion al hashTree del sampler."""
        if assertion.get("type") == "status_code":
            asrt = ET.SubElement(parent, "ResponseAssertion",
                guiclass="AssertionGui", testclass="ResponseAssertion",
                testname="Response Code Assertion", enabled="true")
            coll = ET.SubElement(asrt, "collectionProp", name="Asserion.test_strings")
            ET.SubElement(coll, "stringProp", name="").text = str(assertion.get("value", "200"))
            ET.SubElement(asrt, "stringProp", name="Assertion.custom_message").text = ""
            ET.SubElement(asrt, "stringProp", name="Assertion.test_field").text = "Assertion.response_code"
            ET.SubElement(asrt, "boolProp", name="Assertion.assume_success").text = "false"
            ET.SubElement(asrt, "intProp", name="Assertion.test_type").text = "8"  # Equals
            ET.SubElement(parent, "hashTree")

    def _add_csv_dataset(self, parent: ET.Element, data_file: Dict[str, Any]) -> None:
        """Agregar CSVDataSet al hashTree del ThreadGroup."""
        csv_ds = ET.SubElement(parent, "CSVDataSet",
            guiclass="TestBeanGUI", testclass="CSVDataSet",
            testname=f"CSV - {data_file.get('original_filename', 'data.csv')}", enabled="true")

        ET.SubElement(csv_ds, "stringProp", name="filename").text = data_file.get("file_path", "")
        ET.SubElement(csv_ds, "stringProp", name="variableNames").text = ",".join(
            data_file.get("columns", []))
        ET.SubElement(csv_ds, "boolProp", name="ignoreFirstLine").text = "true"
        ET.SubElement(csv_ds, "stringProp", name="delimiter").text = ","
        ET.SubElement(csv_ds, "boolProp", name="quotedData").text = "true"
        ET.SubElement(csv_ds, "boolProp", name="recycle").text = "true"
        ET.SubElement(csv_ds, "boolProp", name="stopThread").text = "false"
        ET.SubElement(csv_ds, "stringProp", name="shareMode").text = "shareMode.all"
        ET.SubElement(parent, "hashTree")
