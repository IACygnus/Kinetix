"""
Servicio de Análisis con Google Gemini - VERSIÓN MEJORADA
Genera análisis específicos para cada sección del dashboard
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
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        logger.info("GeminiAnalyzer iniciado correctamente")
    
    def analyze_performance(self, metrics: Dict, acceptance_criteria: str = "") -> Dict:
        """Análisis general del performance"""
        try:
            # Construir prompt con métricas
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
            
            # Generar recomendaciones
            recommendations = self._generate_recommendations(metrics, acceptance_criteria)
            
            return {
                'analysis': analysis,
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Error en análisis general: {str(e)}")
            return {
                'analysis': f"Análisis automático: Tasa de error de {metrics['error_rate']:.2f}% con tiempo promedio de {metrics['avg_response_time']:.2f}ms",
                'recommendations': "Se recomienda revisar los resultados detallados."
            }
    
    def analyze_summary_table(self, summary_df, metrics: Dict) -> str:
        """Análisis de la tabla resumen"""
        try:
            # Construir resumen de transacciones
            transactions_summary = []
            for _, row in summary_df.head(10).iterrows():  # Top 10
                transactions_summary.append(
                    f"- {row['label']}: {row['muestras']} requests, "
                    f"{row['errores']} errores ({row['error_pct']:.1f}%), "
                    f"promedio {row['promedio']:.0f}ms"
                )
            
            transactions_text = "\n".join(transactions_summary)
            
            prompt = f"""
Analiza esta tabla de resultados por transacción:

{transactions_text}

RESUMEN GLOBAL:
- Total requests: {metrics['total_requests']:,}
- Tasa de error global: {metrics['error_rate']:.2f}%
- Throughput total: {metrics['throughput']:.2f} req/s

Genera un análisis breve (5 - 6 oraciones) enfocado en:
1. Cuáles transacciones tienen mejor/peor performance
2. Variabilidad de tiempos de respuesta (P99 vs promedio)
3. revisa el total de transacciones y menciona el promedio exitoso y fallido
"""
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error en análisis de tabla: {str(e)}")
            return f"**Variabilidad Moderada:** Los tiempos son relativamente consistentes con el P99 siendo {metrics['p99_response_time']/metrics['avg_response_time']:.1f}x el promedio."
    
    def analyze_errors(self, error_data: List[Dict], total_requests: int) -> str:
        """Análisis de errores"""
        if not error_data or len(error_data) == 0:
            return "✅ No se detectaron errores en la ejecución. El sistema respondió correctamente a todas las solicitudes."
        
        try:
            total_errors = sum(item['count'] for item in error_data)
            error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
            
            errors_summary = []
            for item in error_data[:5]:  # Top 5 errores
                errors_summary.append(
                    f"- {item['label']}: {item['count']} errores (código {item['code']}) - {item['message']}"
                )
            
            errors_text = "\n".join(errors_summary)
            
            prompt = f"""
Analiza estos errores de una prueba de performance:

ERRORES DETECTADOS:
{errors_text}

CONTEXTO:
- Total de errores: {total_errors:,}
- Tasa de error: {error_rate:.2f}%
- Total de requests: {total_requests:,}

Genera un análisis breve (2-3 oraciones) sobre:
1. Tipo de errores (404, 405, 500, etc.)
2. Posibles causas
3. Impacto en el sistema
"""
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error en análisis de errores: {str(e)}")
            return f"Se detectaron {len(error_data)} tipos de errores diferentes. Se recomienda revisar los códigos HTTP y mensajes de error."
    
    def analyze_chart(self, chart_type: str, data_summary: str) -> str:
        """Análisis de gráficos específicos"""
        try:
            prompts = {
                'response_times': f"""
Analiza este gráfico de tiempos de respuesta por transacción:
{data_summary}

Genera 2 oraciones sobre patrones de comportamiento y variaciones entre transacciones.
""",
                'response_time_over_time': f"""
Analiza este gráfico de tiempo de respuesta en el tiempo:
{data_summary}

Genera 2 oraciones sobre tendencias, picos o patrones temporales.
""",
                'throughput': f"""
Analiza este gráfico de throughput:
{data_summary}

Genera 2 oraciones sobre la capacidad del sistema y consistencia.
""",
                'latency': f"""
Analiza este gráfico de latencia:
{data_summary}

Genera 2 oraciones sobre la latencia de red/conexión.
""",
                'error_rate': f"""
Analiza este gráfico de tasa de error:
{data_summary}

Genera 2 oraciones sobre momentos críticos y estabilidad.
""",
                'codes_per_second': f"""
Analiza este gráfico de códigos HTTP por segundo:
{data_summary}

Genera 2 oraciones sobre la distribución de respuestas.
""",
                'transactions_per_second': f"""
Analiza este gráfico de transacciones por segundo:
{data_summary}

Genera 2 oraciones sobre el balance de carga entre transacciones.
""",
                'active_threads': f"""
Analiza este gráfico de threads activos:
{data_summary}

Genera 2 oraciones sobre el escalamiento de concurrencia.
"""
            }
            
            prompt = prompts.get(chart_type, f"Analiza: {data_summary}")
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error en análisis de gráfico {chart_type}: {str(e)}")
            return f"Análisis del gráfico {chart_type} en proceso."
    
    def _generate_recommendations(self, metrics: Dict, acceptance_criteria: str) -> str:
        """Generar recomendaciones basadas en métricas"""
        try:
            criteria_text = f"\n\nCriterios esperados:\n{acceptance_criteria}" if acceptance_criteria else ""
            
            prompt = f"""
Basándote en estas métricas de performance:
- Tasa de error: {metrics['error_rate']:.2f}%
- Tiempo P95: {metrics['p95_response_time']:.2f}ms
- Tiempo promedio: {metrics['avg_response_time']:.2f}ms
- Throughput: {metrics['throughput']:.2f} req/s{criteria_text}

Genera 3-4 recomendaciones técnicas concretas para mejorar el performance.
Usa viñetas (•) para cada recomendación.
"""
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error generando recomendaciones: {str(e)}")
            return "• Revisar logs del servidor para identificar errores\n• Monitorear recursos (CPU, memoria) durante la prueba\n• Considerar optimización de queries o cacheo"

# Instancia global
gemini_analyzer = GeminiAnalyzer()