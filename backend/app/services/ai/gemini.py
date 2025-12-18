"""
Servicio de Análisis con Google Gemini - VERSIÓN MEJORADA
Genera conclusiones y recomendaciones basadas en TODOS los análisis previos
"""
import os
import google.generativeai as genai
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class GeminiAnalyzer:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY no está configurada")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
        logger.info("GeminiAnalyzer iniciado correctamente")
    
    def analyze_performance(self, metrics: Dict, acceptance_criteria: str = "") -> Dict:
        """Análisis general del performance"""
        try:
            criteria_text = f"\n\nCRITERIOS DE ACEPTACIÓN:\n{acceptance_criteria}" if acceptance_criteria else ""
            
            prompt = f"""
Analiza los siguientes resultados de prueba de performance de JMeter:

MÉTRICAS GENERALES:
- Total de requests: {metrics['total_requests']:,}
- Tasa de error: {metrics['error_rate']:.2f}%
- Tiempo promedio de respuesta: {metrics['avg_response_time']:.2f}ms
- Tiempo mínimo: {metrics['min_response_time']:.2f}ms
- Tiempo máximo: {metrics['max_response_time']:.2f}ms
- P95: {metrics['p95_response_time']:.2f}ms
- P99: {metrics['p99_response_time']:.2f}ms
- Throughput: {metrics['throughput']:.2f} req/s
- Duración de la prueba: {metrics['duration_seconds']:.0f} segundos{criteria_text}

Proporciona un análisis técnico breve (máximo 3 párrafos) sobre el performance general.
"""
            
            response = self.model.generate_content(prompt)
            analysis = response.text
            
            return {
                'analysis': analysis
            }
            
        except Exception as e:
            logger.error(f"Error en análisis general: {str(e)}")
            return {
                'analysis': f"Análisis automático: Tasa de error de {metrics['error_rate']:.2f}% con tiempo promedio de {metrics['avg_response_time']:.2f}ms"
            }
    
    def analyze_summary_table(self, summary_df, metrics: Dict) -> str:
        """Análisis MEJORADO de la tabla resumen"""
        try:
            transactions_summary = []
            for _, row in summary_df.head(10).iterrows():
                transactions_summary.append(
                    f"- **{row['label']}**: {int(row['muestras'])} muestras ejecutadas, "
                    f"{int(row['errores'])} errores ({row['tasa_error']:.2f}% error rate), "
                    f"tiempo promedio {row['promedio']:.0f}ms, "
                    f"P95 {row['p95']:.0f}ms, "
                    f"rendimiento {row['rendimiento']:.2f} req/s"
                )
            
            transactions_text = "\n".join(transactions_summary)
            
            prompt = f"""
Analiza esta tabla de resultados por transacción de una prueba de performance JMeter:

TRANSACCIONES:
{transactions_text}

RESUMEN GLOBAL:
- Total de muestras/transacciones ejecutadas: {metrics['total_requests']:,}
- Tasa de error global: {metrics['error_rate']:.2f}%
- Tiempo promedio global: {metrics['avg_response_time']:.2f}ms
- Percentil 95 global: {metrics['p95_response_time']:.2f}ms
- Throughput/Rendimiento total: {metrics['throughput']:.2f} req/s

Genera un análisis profesional (6-8 oraciones) que incluya:
1. Número total de transacciones ejecutadas y muestras
2. Cuáles transacciones tienen mejor/peor performance (menciona nombres específicos)
3. Análisis de variabilidad (compara P95 vs promedio, menciona el ratio)
4. Análisis del rendimiento (throughput/req por segundo)
5. Menciona específicamente cuántas transacciones fueron exitosas vs fallidas
6. Identifica patrones o comportamientos destacables

Sé específico con números y nombres de transacciones.
"""
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error en análisis de tabla: {str(e)}")
            return f"Se ejecutaron {metrics['total_requests']:,} transacciones con una tasa de error de {metrics['error_rate']:.2f}%. El tiempo promedio fue {metrics['avg_response_time']:.2f}ms con P95 de {metrics['p95_response_time']:.2f}ms."
    
    def analyze_errors(self, error_data: List[Dict], total_requests: int) -> str:
        """Análisis MEJORADO de errores"""
        if not error_data or len(error_data) == 0:
            return "✅ No se detectaron errores en la ejecución. El sistema respondió correctamente a todas las solicitudes."
        
        try:
            total_errors = sum(item['count'] for item in error_data)
            error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
            
            errors_by_transaction = []
            for item in error_data[:10]:
                errors_by_transaction.append(
                    f"- **{item['label']}**: {item['count']} errores (código HTTP {item['code']}) "
                    f"- {(item['count']/total_requests*100):.2f}% del total de requests"
                )
            
            errors_text = "\n".join(errors_by_transaction)
            
            prompt = f"""
Analiza estos errores detectados en una prueba de performance JMeter:

ERRORES POR TRANSACCIÓN:
{errors_text}

CONTEXTO:
- Total de errores detectados: {total_errors:,}
- Tasa de error global: {error_rate:.2f}%
- Total de requests ejecutados: {total_requests:,}
- Número de transacciones con errores: {len(error_data)}

Genera un análisis profesional (5-6 oraciones) que incluya:
1. Cantidad total de errores y porcentaje
2. Tipos de códigos HTTP detectados (404, 405, 500, etc.) y qué significan
3. Cuáles transacciones específicas tienen más errores (menciona nombres)
4. Posibles causas técnicas de estos errores
5. Impacto en la funcionalidad del sistema
6. Recomendación inmediata

Sé específico con números, porcentajes y nombres de transacciones.
"""
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error en análisis de errores: {str(e)}")
            return f"Se detectaron {total_errors:,} errores ({error_rate:.2f}%) distribuidos en {len(error_data)} transacciones diferentes. Se recomienda revisar los códigos HTTP y mensajes de error."
    
    def analyze_chart(self, chart_type: str, data_summary: str) -> str:
        """Análisis MEJORADO de gráficos específicos"""
        try:
            prompts = {
                'response_times': f"""
Analiza este gráfico de tiempos de respuesta por transacción:

{data_summary}

Genera un análisis profesional (3-4 oraciones) que incluya:
1. Cuáles transacciones tienen mejor/peor performance (menciona nombres y tiempos específicos)
2. Compara tiempos promedio vs P95 para identificar variabilidad
3. Identifica patrones o comportamientos destacables
4. Da una conclusión sobre la consistencia del sistema

Sé específico con números y nombres.
""",
                'response_time_over_time': f"""
Analiza este gráfico de tiempo de respuesta a lo largo del tiempo:

{data_summary}

Genera un análisis profesional (3-4 oraciones) sobre:
1. Tendencias observadas (¿mejora, empeora, se mantiene estable?)
2. Picos o degradación del performance
3. Patrones temporales o estacionalidad
4. Conclusión sobre estabilidad del sistema bajo carga

Incluye números específicos de tiempos.
""",
                'throughput': f"""
Analiza este gráfico de throughput (rendimiento):

{data_summary}

Genera un análisis profesional (3-4 oraciones) sobre:
1. Capacidad del sistema (requests por segundo)
2. Consistencia del throughput durante la prueba
3. Si el sistema mantuvo el rendimiento o decayó
4. Conclusión sobre escalabilidad

Incluye números específicos de req/s.
""",
                'latency': f"""
Analiza este gráfico de latencia de red:

{data_summary}

Genera un análisis profesional (3-4 oraciones) sobre:
1. Latencia promedio observada
2. Impacto de la latencia en el tiempo total de respuesta
3. Variabilidad de la latencia
4. Conclusión sobre la conectividad

Incluye números específicos de latencia.
""",
                'error_rate': f"""
Analiza este gráfico de tasa de error a lo largo del tiempo:

{data_summary}

Genera un análisis profesional (3-4 oraciones) sobre:
1. Comportamiento de los errores (constantes, intermitentes, crecientes)
2. Momentos críticos donde aumentaron los errores
3. Estabilidad del sistema
4. Conclusión sobre confiabilidad

Incluye porcentajes y números específicos.
""",
                'codes_per_second': f"""
Analiza este gráfico de códigos HTTP por segundo:

{data_summary}

Genera un análisis profesional (3-4 oraciones) sobre:
1. Distribución de códigos de respuesta (2xx, 4xx, 5xx)
2. Proporción de respuestas exitosas vs errores
3. Patrones en los códigos HTTP
4. Conclusión sobre salud del sistema

Incluye números específicos de códigos HTTP.
""",
                'transactions_per_second': f"""
Analiza este gráfico de transacciones por segundo (TPS):

{data_summary}

Genera un análisis profesional (3-4 oraciones) sobre:
1. Distribución de carga entre transacciones
2. Balance o desbalance de TPS
3. Cuáles transacciones tienen mayor volumen
4. Conclusión sobre distribución de carga

Incluye TPS específicos por transacción.
""",
                'active_threads': f"""
Analiza este gráfico de hilos/usuarios activos:

{data_summary}

Genera un análisis profesional (3-4 oraciones) sobre:
1. Comportamiento de la concurrencia
2. Ramp-up y estabilización de usuarios
3. Capacidad del sistema para manejar concurrencia
4. Conclusión sobre escalamiento

Incluye números específicos de usuarios/threads.
"""
            }
            
            prompt = prompts.get(chart_type, f"Analiza: {data_summary}")
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error en análisis de gráfico {chart_type}: {str(e)}")
            return f"Análisis del gráfico {chart_type}: {data_summary}"
    
    def generate_conclusions(
        self, 
        metrics: Dict,
        ai_analysis_summary: str,
        ai_analysis_errors: str,
        ai_analysis_response_times: str,
        ai_analysis_response_time_over_time: str,
        ai_analysis_throughput: str,
        ai_analysis_latency: str,
        ai_analysis_error_rate: str,
        ai_analysis_codes_per_second: str,
        ai_analysis_transactions_per_second: str,
        ai_analysis_active_threads: str
    ) -> str:
        """✅ NUEVO: Generar conclusiones SINTETIZANDO todos los análisis previos"""
        try:
            prompt = f"""
Eres un experto en performance testing. Acabas de analizar una prueba de JMeter en profundidad.

MÉTRICAS CLAVE:
- Total requests: {metrics['total_requests']:,}
- Error rate: {metrics['error_rate']:.2f}%
- Avg time: {metrics['avg_response_time']:.2f}ms
- P95: {metrics['p95_response_time']:.2f}ms
- Throughput: {metrics['throughput']:.2f} req/s
- Duración: {metrics['duration_seconds']:.0f}s

ANÁLISIS REALIZADOS:

1. TABLA RESUMEN:
{ai_analysis_summary[:300]}...

2. ERRORES:
{ai_analysis_errors[:300]}...

3. RESPONSE TIMES POR TRANSACCIÓN:
{ai_analysis_response_times[:200]}...

4. RESPONSE TIME OVER TIME:
{ai_analysis_response_time_over_time[:200]}...

5. THROUGHPUT:
{ai_analysis_throughput[:200]}...

6. LATENCY:
{ai_analysis_latency[:200]}...

7. ERROR RATE:
{ai_analysis_error_rate[:200]}...

8. CÓDIGOS HTTP:
{ai_analysis_codes_per_second[:200]}...

9. TPS:
{ai_analysis_transactions_per_second[:200]}...

10. ACTIVE THREADS:
{ai_analysis_active_threads[:200]}...

TAREA:
Sintetiza TODOS estos análisis en 4-5 conclusiones generales ejecutivas.

Cada conclusión debe:
1. Sintetizar múltiples análisis relacionados
2. Ser específica con números reales
3. Dar un veredicto claro (exitoso/fallido/aceptable/requiere atención)
4. Ser accionable para el equipo técnico

Formato:
• [Conclusión sobre performance general basada en tiempos, tabla, gráficos]
• [Conclusión sobre errores y estabilidad basada en errores, codes, error rate]
• [Conclusión sobre capacidad basada en throughput, TPS, threads]
• [Conclusión sobre consistencia basada en variabilidad de tiempos, latencia]
• [Veredicto final: ¿La prueba fue exitosa? ¿Qué sigue?]
"""
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error generando conclusiones: {str(e)}")
            return f"• La prueba procesó {metrics['total_requests']:,} requests con {metrics['error_rate']:.2f}% de tasa de error\n• El tiempo promedio de respuesta fue {metrics['avg_response_time']:.2f}ms con P95 de {metrics['p95_response_time']:.2f}ms\n• El throughput alcanzado fue de {metrics['throughput']:.2f} req/s durante {metrics['duration_seconds']:.0f} segundos"
    
    def generate_recommendations(
        self,
        metrics: Dict,
        ai_analysis_summary: str,
        ai_analysis_errors: str,
        ai_analysis_response_times: str,
        ai_analysis_response_time_over_time: str,
        ai_analysis_throughput: str,
        ai_analysis_latency: str,
        ai_analysis_error_rate: str,
        ai_analysis_codes_per_second: str,
        ai_analysis_transactions_per_second: str,
        ai_analysis_active_threads: str
    ) -> str:
        """✅ NUEVO: Generar recomendaciones basadas en TODOS los análisis"""
        try:
            prompt = f"""
Eres un arquitecto de software senior analizando una prueba de performance JMeter.

MÉTRICAS CLAVE:
- Total requests: {metrics['total_requests']:,}
- Error rate: {metrics['error_rate']:.2f}%
- Avg time: {metrics['avg_response_time']:.2f}ms
- P95: {metrics['p95_response_time']:.2f}ms
- P99: {metrics['p99_response_time']:.2f}ms
- Throughput: {metrics['throughput']:.2f} req/s

HALLAZGOS DE ANÁLISIS:

TABLA & TRANSACCIONES:
{ai_analysis_summary[:300]}

ERRORES DETECTADOS:
{ai_analysis_errors[:300]}

PATRONES DE TIEMPOS:
{ai_analysis_response_times[:200]}
{ai_analysis_response_time_over_time[:200]}

CAPACIDAD:
{ai_analysis_throughput[:200]}
{ai_analysis_transactions_per_second[:200]}

INFRAESTRUCTURA:
{ai_analysis_latency[:200]}
{ai_analysis_active_threads[:200]}

TAREA:
Genera 5-6 recomendaciones técnicas ACCIONABLES basadas en los patrones identificados.

Cada recomendación debe:
1. Basarse en hallazgos específicos de los análisis
2. Ser técnica y concreta (qué hacer exactamente)
3. Incluir números/métricas específicas
4. Explicar el impacto esperado
5. Priorizar por impacto (crítico > alto > medio)

Formato:
• [CRÍTICO/ALTO/MEDIO] [Acción específica] porque [hallazgo] → impacto: [resultado esperado]

Ejemplos:
• CRÍTICO: Corregir endpoints que generan errores 404/405 en transacción X (27% error rate) → impacto: reducir error rate de 27% a <5%
• ALTO: Optimizar transacción Y que tiene P95 de 2500ms → impacto: mejorar experiencia del 95% de usuarios
"""
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error generando recomendaciones: {str(e)}")
            return f"• Revisar logs del servidor para identificar la causa de los {metrics['total_errors']} errores detectados\n• Optimizar transacciones con tiempos superiores a {metrics['p95_response_time']:.0f}ms (P95)\n• Monitorear recursos del servidor durante cargas de {metrics['throughput']:.0f} req/s\n• Considerar implementar caché o CDN para mejorar tiempos de respuesta"

# Instancia global
gemini_analyzer = GeminiAnalyzer()