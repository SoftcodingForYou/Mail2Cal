"""
AI-powered email content parser for extracting event information
"""

import os
import json
from typing import List, Dict, Optional
from datetime import datetime
import openai
import anthropic


class AIEmailParser:
    def __init__(self, config: Dict):
        self.config = config
        self.ai_config = config['ai_service']
        self.client = self._initialize_ai_client()
    
    def _initialize_ai_client(self):
        """Initialize AI client based on configuration"""
        provider = self.ai_config['provider']
        api_key = os.getenv(self.ai_config['api_key_env_var'])
        
        if not api_key:
            raise ValueError(f"API key not found in environment variable: {self.ai_config['api_key_env_var']}")
        
        if provider == "openai":
            return openai.OpenAI(api_key=api_key)
        elif provider == "anthropic":
            return anthropic.Anthropic(api_key=api_key)
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")
    
    def parse_email_for_events(self, email: Dict, sender_type: str = 'other') -> List[Dict]:
        """Use AI to parse email content and extract event information"""
        
        prompt = self._build_parsing_prompt(email, sender_type)
        
        try:
            if self.ai_config['provider'] == "openai":
                response = self._query_openai(prompt)
            else:
                response = self._query_anthropic(prompt)
            
            # Parse the AI response
            events = self._parse_ai_response(response, email)
            return events
            
        except Exception as e:
            print(f"Error parsing email with AI: {e}")
            return []
    
    def _build_parsing_prompt(self, email: Dict, sender_type: str = 'other') -> str:
        """Build a comprehensive prompt for AI parsing"""
        current_year = datetime.now().year
        
        # Define default times based on sender type
        default_time_guidance = ""
        if sender_type in ['teacher_1', 'teacher_2']:
            default_time_guidance = """
HORARIO POR DEFECTO PARA EVENTOS SIN HORA ESPECIFICADA (PROFESORES 1 Y 2):
- Si NO se especifica hora, establecer start_time como "08:00" y end_time como "10:00" (2 horas de duración)
- Solo usar all_day: true si específicamente se menciona que es "todo el día" o similar
"""
        elif sender_type == 'afterschool':
            default_time_guidance = """
HORARIO POR DEFECTO PARA EVENTOS DE AFTERSCHOOL SIN HORA ESPECIFICADA (PROFESORES 3 Y 4):
- Si NO se especifica hora, establecer start_time como "13:00" y end_time como "15:00" (2 horas de duración)
- Solo usar all_day: true si específicamente se menciona que es "todo el día" o similar
"""
        else:
            default_time_guidance = """
HORARIO POR DEFECTO PARA OTROS REMITENTES:
- Si NO se especifica hora, usar all_day: true
"""
        
        # Check if email has PDF attachments
        has_pdf_content = "=== CONTENIDO DEL ARCHIVO PDF:" in email['body']
        pdf_notice = ""
        if has_pdf_content:
            pdf_notice = """
NOTA IMPORTANTE: Este email incluye contenido extraído de archivos PDF adjuntos.
El contenido PDF puede contener información crucial sobre:
- Días feriados y suspensión de clases
- Actividades especiales programadas
- Cambios en el calendario escolar
- Horarios especiales o excepcionales
Presta especial atención al contenido marcado como "CONTENIDO DEL ARCHIVO PDF".
"""

        
        prompt = f"""
Analiza el siguiente email del colegio y extrae TODA la información de eventos. Este es un contexto de jardín infantil.
{pdf_notice}
DETALLES DEL EMAIL:
Asunto: {email['subject']}
De: {email['sender']}
Fecha: {email['date']}
Contenido: {email['body']}

TAREA: Extraer todos los eventos, actividades, tareas, fechas límite, reuniones, presentaciones, o cualquier información sensible al tiempo.
ESPECIAL ATENCIÓN: Si hay contenido de archivos PDF, este puede contener días feriados, actividades especiales o cambios importantes en el calendario.

Para cada evento encontrado, proporciona una respuesta JSON con esta estructura exacta:
{{
  "events": [
    {{
      "title": "Título claro y conciso del evento EN ESPAÑOL CHILENO FORMAL",
      "description": "Descripción detallada incluyendo toda la información relevante del email EN ESPAÑOL CHILENO FORMAL",
      "start_date": "YYYY-MM-DD",
      "start_time": "HH:MM" o null si no se especifica,
      "end_date": "YYYY-MM-DD" o null si es igual a start_date,
      "end_time": "HH:MM" o null si no se especifica,
      "all_day": true/false,
      "location": "ubicación si se menciona" o null,
      "event_type": "tarea|reunion|actividad|ceremonia|presentacion|general",
      "priority": "alta|media|baja",
      "recurring": true/false,
      "notes": "Cualquier detalle adicional importante EN ESPAÑOL CHILENO FORMAL"
    }}
  ]
}}

{default_time_guidance}

DIRECTRICES IMPORTANTES:
1. Si no se menciona año específico, asumir {current_year}
2. Aplicar las reglas de horario por defecto según el tipo de remitente (ver arriba)
3. Buscar formatos de fecha en español: "15 de marzo", "viernes 20", etc.
4. Extraer fechas límite de tareas, fechas de entrega de proyectos y entregas
5. Incluir reuniones de apoderados, eventos escolares y fechas límite administrativas
6. Si se mencionan rangos de tiempo (ej: "de 9:00 a 11:00"), establecer start_time y end_time
7. Para eventos recurrentes, establecer recurring como true y anotar el patrón en description
8. Si no se encuentran eventos, devolver {{"events": []}}
9. IMPORTANTE: TODO el texto debe estar en ESPAÑOL CHILENO FORMAL (usar "usted", evitar anglicismos)

REGLAS ESPECIALES PARA ACTIVIDADES EXTRAESCOLARES Y TALLERES:
- FORMATO TABULAR: Si el contenido está en formato de tabla con columnas de días (LUNES, MARTES, MIÉRCOLES, JUEVES, VIERNES, SÁBADO, DOMINGO), analizar cuidadosamente qué actividad pertenece a qué columna
- Cada actividad debe programarse para el día correcto según su columna en la tabla
- OBLIGATORIO: Establecer recurring: true para todas las actividades que mencionan días de la semana
- En "notes" agregar claramente: "Actividad recurrente - todos los [DÍA] del segundo semestre 2025"
- Para actividades del "segundo semestre", la fecha de inicio debe ser el próximo [DÍA] de la semana después del 15 de julio de {current_year}

MAPEO DE DÍAS PARA CÁLCULO DE FECHAS:
- LUNES → Próximo lunes disponible después del 15 de julio de {current_year}
- MARTES → Próximo martes disponible después del 15 de julio de {current_year}  
- MIÉRCOLES → Próximo miércoles disponible después del 15 de julio de {current_year}
- JUEVES → Próximo jueves disponible después del 15 de julio de {current_year}
- VIERNES → Próximo viernes disponible después del 15 de julio de {current_year}
- SÁBADO → Próximo sábado disponible después del 15 de julio de {current_year}
- DOMINGO → Próximo domingo disponible después del 15 de julio de {current_year}

HORARIOS: Si se especifica un rango de tiempo (ej: "15:30 A 17:00 HRS"), usar esas horas exactas, NO marcar como all_day

EJEMPLO DE INTERPRETACIÓN TABULAR:
Si ves una tabla como:
LUNES          MARTES         MIÉRCOLES
CHEERLEADERS   FUTBOL         ARTE
15:30 A 17:00  14:00 A 15:30  13:00 A 14:30

Entonces:
- CHEERLEADERS va el LUNES de 15:30 a 17:00
- FUTBOL va el MARTES de 14:00 a 15:30  
- ARTE va el MIÉRCOLES de 13:00 a 14:30

CONTEXTO: Este es para un jardín infantil chileno, así que espera idioma español y formatos de fecha/hora chilenos.

IMPORTANTE: Usa solo caracteres ASCII en el JSON. Reemplaza acentos (á→a, é→e, í→i, ó→o, ú→u, ñ→n) para evitar errores de codificación.

Responde SOLO con JSON válido, sin texto adicional.
"""
        return prompt
    
    def _query_openai(self, prompt: str) -> str:
        """Query OpenAI API"""
        response = self.client.chat.completions.create(
            model=self.ai_config['model'],
            messages=[
                {"role": "system", "content": "You are an expert at extracting structured event information from educational emails. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=3000
        )
        return response.choices[0].message.content
    
    def _query_anthropic(self, prompt: str) -> str:
        """Query Anthropic API"""
        response = self.client.messages.create(
            model=self.ai_config['model'],
            max_tokens=3000,
            temperature=0.1,
            system="You are an expert at extracting structured event information from educational emails. Always respond with valid JSON only.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.content[0].text
    
    def _parse_ai_response(self, response: str, email: Dict) -> List[Dict]:
        """Parse the AI response and convert to internal event format"""
        try:
            # Clean the response to ensure it's valid JSON
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            
            # Handle truncated JSON responses
            if not response.rstrip().endswith('}') and not response.rstrip().endswith(']'):
                print("[!] Response appears truncated, attempting to fix...")
                
                # Find the last complete event and truncate there
                last_complete_event = -1
                lines = response.split('\n')
                
                for i, line in enumerate(lines):
                    if line.strip() == '},' or (line.strip() == '}' and i < len(lines) - 3):
                        last_complete_event = i
                
                if last_complete_event > 0:
                    # Truncate to last complete event
                    response = '\n'.join(lines[:last_complete_event + 1])
                    
                    # Remove trailing comma and close properly
                    response = response.rstrip().rstrip(',')
                    response += '\n  ]\n}'
                else:
                    # Fallback: simple bracket counting
                    open_braces = response.count('{') - response.count('}')
                    open_brackets = response.count('[') - response.count(']')
                    
                    # Remove any incomplete trailing content
                    if response.rstrip().endswith(','):
                        response = response.rstrip().rstrip(',')
                    
                    # Close structures
                    response += '}' * open_braces + ']' * open_brackets
            
            data = json.loads(response)
            events = []
            
            for event_data in data.get('events', []):
                event = self._convert_ai_event_to_internal(event_data, email)
                if event:
                    events.append(event)
            
            return events
            
        except json.JSONDecodeError as e:
            print(f"Error parsing AI response as JSON: {e}")
            print(f"Response was: {response}")
            return []
        except Exception as e:
            print(f"Error processing AI response: {e}")
            return []
    
    def _convert_ai_event_to_internal(self, ai_event: Dict, email: Dict) -> Optional[Dict]:
        """Convert AI-parsed event to internal event format"""
        try:
            # Parse dates
            start_datetime = self._parse_event_datetime(
                ai_event.get('start_date'),
                ai_event.get('start_time')
            )
            
            end_datetime = None
            if ai_event.get('end_date') or ai_event.get('end_time'):
                end_datetime = self._parse_event_datetime(
                    ai_event.get('end_date') or ai_event.get('start_date'),
                    ai_event.get('end_time')
                )
            
            # Build comprehensive description
            description = self._build_event_description(ai_event, email)
            
            return {
                'summary': ai_event.get('title', 'Evento Escolar'),
                'description': description,
                'start_time': start_datetime,
                'end_time': end_datetime,
                'all_day': ai_event.get('all_day', False),
                'location': ai_event.get('location'),
                'source_email_id': email['id'],
                'source_email_subject': email['subject'],
                'source_email_date': email['date'],
                'event_type': ai_event.get('event_type', 'general'),
                'priority': ai_event.get('priority', 'medium'),
                'recurring': ai_event.get('recurring', False),
                'ai_notes': ai_event.get('notes', ''),
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error converting AI event: {e}")
            return None
    
    def _parse_event_datetime(self, date_str: str, time_str: str = None) -> Optional[datetime]:
        """Parse date and time strings into datetime object"""
        if not date_str:
            return None
        
        try:
            # Parse date
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Parse time if provided
            if time_str:
                time_obj = datetime.strptime(time_str, '%H:%M').time()
                return datetime.combine(date_obj, time_obj)
            else:
                return datetime.combine(date_obj, datetime.min.time())
                
        except ValueError as e:
            print(f"Error parsing datetime: {date_str} {time_str} - {e}")
            return None
    
    def _build_event_description(self, ai_event: Dict, email: Dict) -> str:
        """Build comprehensive event description with source information"""
        
        description_parts = []
        
        # Main event description
        if ai_event.get('description'):
            description_parts.append(ai_event['description'])
        
        # Additional notes from AI
        if ai_event.get('notes'):
            description_parts.append(f"\nNotas adicionales: {ai_event['notes']}")
        
        # Source email information
        description_parts.append(f"\n{'='*50}")
        description_parts.append(f"INFORMACIÓN DEL EMAIL FUENTE:")
        description_parts.append(f"Asunto: {email['subject']}")
        description_parts.append(f"Fecha del email: {email['date']}")
        description_parts.append(f"Remitente: {email['sender']}")
        description_parts.append(f"ID del email: {email['id']}")
        
        # Event metadata
        if ai_event.get('event_type'):
            description_parts.append(f"Tipo de evento: {ai_event['event_type']}")
        if ai_event.get('priority'):
            description_parts.append(f"Prioridad: {ai_event['priority']}")
        if ai_event.get('recurring'):
            description_parts.append("Evento recurrente: Sí")
        
        description_parts.append(f"Procesado por Mail2Cal el: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        return '\n'.join(description_parts)