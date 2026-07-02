from collections import defaultdict

from googledrive.models import GoogleDriveFile
from googledrive.models import GoogleDriveFileDocument
 

FOLDER_MIME = "application/vnd.google-apps.folder"

from django.db.models import Q
from django.contrib.postgres.search import SearchQuery
from django.http import JsonResponse
from django.core.serializers import serialize
import json

import logging

logger = logging.getLogger(__name__) 

def buscar_tokens(search_string):
    """
    Busca coincidencias en archivos de Google Drive basándose en un string de búsqueda.
    
    Args:
        search_string (str): String de búsqueda que puede contener varias palabras
                            Ejemplo: "contratos de compra 2027"
    
    Returns:
        JsonResponse: JSON con los resultados de la búsqueda
    """
    # Limpiar el string de búsqueda
    search_terms = search_string.strip().split()
    
    if not search_terms:
        return JsonResponse({
            'status': 'error',
            'message': 'El término de búsqueda no puede estar vacío',
            'results': []
        })
    
    # Construir la consulta para búsqueda en texto completo (search_vector)
    search_query = SearchQuery(search_string, config='spanish')
    
    # Búsqueda en campos de GoogleDriveFile
    name_queries = Q()
    for term in search_terms:
        name_queries |= Q(name__icontains=term)
    
    # Búsqueda en parent_drive_file_id.name (nombre de la carpeta padre)
    parent_name_queries = Q()
    for term in search_terms:
        parent_name_queries |= Q(parent_drive_file_id__name__icontains=term)
    
    # Consulta principal combinando todas las condiciones
    # Usamos distinct() para evitar duplicados
    files = GoogleDriveFile.objects.filter(
        Q(name_queries) |
        Q(parent_name_queries) |
        Q(document__search_vector=search_query) |
        Q(document__description_vector=search_query)
    ).distinct().select_related('parent_drive_file_id', 'document')
    
    # Construir los resultados
    results = []
    for file in files:
        result = {
            'id': str(file.id),
            'drive_file_id': file.drive_file_id,
            'name': file.name,
            'mime_type': file.mime_type,
            'parent_drive_file_id': file.parent_drive_file_id.drive_file_id if file.parent_drive_file_id else None,
            'parent_name': file.parent_drive_file_id.name if file.parent_drive_file_id else None,
            'drive_web_view_link': file.drive_web_view_link,
            'last_known_modified_time': file.last_known_modified_time.isoformat() if file.last_known_modified_time else None,
            'last_synced_at': file.last_synced_at.isoformat() if file.last_synced_at else None,
        }
        
        # Agregar información del documento si existe
        if hasattr(file, 'document') and file.document:
            result['text_content_preview'] = file.document.text_content[:500] if file.document.text_content else None
            result['description'] = file.document.description
            result['area'] = file.area_id if file.area else None
        
        # Determinar en qué campos se encontraron coincidencias
        matches = []
        # Verificar coincidencias en name
        if any(term.lower() in file.name.lower() for term in search_terms):
            matches.append('name')
        
        # Verificar coincidencias en parent name
        if file.parent_drive_file_id and any(term.lower() in file.parent_drive_file_id.name.lower() for term in search_terms):
            matches.append('parent_name')
        
        # Verificar coincidencias en search_vector
        if hasattr(file, 'document') and file.document and file.document.search_vector:
            # Verificar si el search_query coincide con el search_vector
            if GoogleDriveFileDocument.objects.filter(file=file, search_vector=search_query).exists():
                matches.append('search_vector')
        
        # Verificar coincidencias en description_vector
        if hasattr(file, 'document') and file.document and file.document.description_vector:
            if GoogleDriveFileDocument.objects.filter(file=file, description_vector=search_query).exists():
                matches.append('description_vector')
        
        # Agregar información de coincidencias
        result['matches_found_in'] = matches
        result['relevance_score'] = len(matches)
        
        results.append(result)
    
    # Ordenar resultados por relevancia (cantidad de campos donde coincidió)
    results.sort(key=lambda x: x['relevance_score'], reverse=True)
    
    return JsonResponse({
        'status': 'success',
        'search_string': search_string,
        'total_results': len(results),
        'results': results
    }, json_dumps_params={'ensure_ascii': False})

# Función alternativa que retorna un diccionario en lugar de JsonResponse
def search_google_drive_files_dict(search_string):
    """
    Versión que retorna un diccionario en lugar de JsonResponse.
    Útil para usar en otras partes de la aplicación.
    """
    search_terms = search_string.strip().split()
    
    if not search_terms:
        return {
            'status': 'error',
            'message': 'El término de búsqueda no puede estar vacío',
            'results': []
        }
    
    search_query = SearchQuery(search_string, config='spanish')
    
    name_queries = Q()
    for term in search_terms:
        name_queries |= Q(name__icontains=term)
    
    parent_name_queries = Q()
    for term in search_terms:
        parent_name_queries |= Q(parent_drive_file_id__name__icontains=term)
    
    files = GoogleDriveFile.objects.filter(
        Q(name_queries) |
        Q(parent_name_queries) |
        Q(document__search_vector=search_query) |
        Q(document__description_vector=search_query)
    ).distinct().select_related('parent_drive_file_id', 'document')
    
    results = []
    for file in files:
        result = {
            'id': str(file.id),
            'drive_file_id': file.drive_file_id,
            'name': file.name,
            'mime_type': file.mime_type,
            'parent_drive_file_id': file.parent_drive_file_id.drive_file_id if file.parent_drive_file_id else None,
            'parent_name': file.parent_drive_file_id.name if file.parent_drive_file_id else None,
            'drive_web_view_link': file.drive_web_view_link,
            'last_known_modified_time': file.last_known_modified_time.isoformat() if file.last_known_modified_time else None,
            'last_synced_at': file.last_synced_at.isoformat() if file.last_synced_at else None,
        }
        
        if hasattr(file, 'document') and file.document:
            result['text_content_preview'] = file.document.text_content[:500] if file.document.text_content else None
            result['description'] = file.document.description
            result['area'] = file.area_id if file.area else None
        
        matches = []
        if any(term.lower() in file.name.lower() for term in search_terms):
            matches.append('name')
        
        if file.parent_drive_file_id and any(term.lower() in file.parent_drive_file_id.name.lower() for term in search_terms):
            matches.append('parent_name')
        
        if hasattr(file, 'document') and file.document and file.document.search_vector:
            if GoogleDriveFileDocument.objects.filter(file=file, search_vector=search_query).exists():
                matches.append('search_vector')
        
        if hasattr(file, 'document') and file.document and file.document.description_vector:
            if GoogleDriveFileDocument.objects.filter(file=file, description_vector=search_query).exists():
                matches.append('description_vector')
        
        result['matches_found_in'] = matches
        result['relevance_score'] = len(matches)
        
        results.append(result)
    
    results.sort(key=lambda x: x['relevance_score'], reverse=True)
    
    return {
        'status': 'success',
        'search_string': search_string,
        'total_results': len(results),
        'results': results
    }



from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector, SearchVectorField
from django.db.models import Q, Value, FloatField, F
from django.db.models.functions import Coalesce
from django.http import JsonResponse

def search_google_drive_files_ranked_v0(search_string):
    """
    Búsqueda con ranking de relevancia usando PostgreSQL SearchRank
     
    """
    search_terms = search_string.strip().split()
    
    if not search_terms:
        return JsonResponse({
            'status': 'error',
            'message': 'El término de búsqueda no puede estar vacío',
            'results': []
        })
    
    # Configurar la búsqueda en español
    search_query = SearchQuery(search_string, config='spanish')
    
    # Construir queries para búsqueda en texto
    name_queries = Q()
    for term in search_terms:
        name_queries |= Q(name__icontains=term)
    
    parent_name_queries = Q()
    for term in search_terms:
        parent_name_queries |= Q(parent_drive_file_id__name__icontains=term)
    
    # Búsqueda principal con anotación de ranking
    files = GoogleDriveFile.objects.filter(
        Q(name_queries) |
        Q(parent_name_queries) |
        Q(document__search_vector=search_query) |
        Q(document__description_vector=search_query)
    ).distinct().select_related('parent_drive_file_id', 'document', 'area').annotate(
        # Convertir name a tsvector y calcular rank
        name_rank=SearchRank(
            SearchVector('name', config='spanish'), 
            search_query
        ),
        # Convertir parent name a tsvector
        parent_rank=SearchRank(
            SearchVector('parent_drive_file_id__name', config='spanish'), 
            search_query
        ),
        # Usar search_vector directamente (ya es tsvector)
        search_vector_rank=SearchRank(
            F('document__search_vector'), 
            search_query
        ),
        # Usar description_vector directamente
        description_rank=SearchRank(
            F('document__description_vector'), 
            search_query
        ),
        # Sumar todas las relevancias
        total_rank=(
            Coalesce('name_rank', Value(0.0, output_field=FloatField())) + 
            Coalesce('parent_rank', Value(0.0, output_field=FloatField())) + 
            Coalesce('search_vector_rank', Value(0.0, output_field=FloatField())) + 
            Coalesce('description_rank', Value(0.0, output_field=FloatField()))
        )
    ).order_by('-total_rank')
    
    # Construir resultados
    results = []
    for file in files:
        matches = []
        if any(term.lower() in file.name.lower() for term in search_terms):
            matches.append('name')
        
        if file.parent_drive_file_id and any(term.lower() in file.parent_drive_file_id.name.lower() for term in search_terms):
            matches.append('parent_name')
        
        if hasattr(file, 'document') and file.document:
            if file.document.search_vector:
                if GoogleDriveFileDocument.objects.filter(file=file, search_vector=search_query).exists():
                    matches.append('search_vector')
            
            if file.document.description_vector:
                if GoogleDriveFileDocument.objects.filter(file=file, description_vector=search_query).exists():
                    matches.append('description_vector')
        
        result = {
            'id': str(file.id),
            'drive_file_id': file.drive_file_id,
            'name': file.name,
            'mime_type': file.mime_type,
            'parent_drive_file_id': file.parent_drive_file_id.drive_file_id if file.parent_drive_file_id else None,
            'parent_name': file.parent_drive_file_id.name if file.parent_drive_file_id else None,
            'drive_web_view_link': file.drive_web_view_link,
            'last_known_modified_time': file.last_known_modified_time.isoformat() if file.last_known_modified_time else None,
            'last_synced_at': file.last_synced_at.isoformat() if file.last_synced_at else None,
            'relevance_score': float(file.total_rank) if file.total_rank else 0,
            'relevance_details': {
                'name_rank': float(file.name_rank) if file.name_rank else 0,
                'parent_rank': float(file.parent_rank) if file.parent_rank else 0,
                'search_vector_rank': float(file.search_vector_rank) if file.search_vector_rank else 0,
                'description_rank': float(file.description_rank) if file.description_rank else 0,
            },
            'matches_found_in': matches,
            'area': file.area_id if file.area else None,
            'area_name': file.area.nombre if file.area else None,
        }
        
        if hasattr(file, 'document') and file.document:
            result['document'] = {
                'text_content_preview': file.document.text_content[:500] if file.document.text_content else None,
                'description': file.document.description,
            }
        
        results.append(result)
    
    return JsonResponse({
        'status': 'success',
        'search_string': search_string,
        'total_results': len(results),
        'results': results
    }, json_dumps_params={'ensure_ascii': False})


from django.db.models import Q, F, Value, FloatField, Case, When
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models.functions import Coalesce
from django.http import JsonResponse

from django.db.models import Q, F, Value, FloatField, Case, When
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models.functions import Coalesce
from django.http import JsonResponse

def search_google_drive_files_ranked_v1(search_string):
    """
    Búsqueda con ranking de relevancia y extracción de textos coincidentes
    1) Primero busca exactamente el string ingresado y da el ranking mayor
    2) Luego usa search_string.split() para búsqueda más amplia
    """
    search_terms = search_string.strip().split()
    
    if not search_terms:
        return JsonResponse({
            'status': 'error',
            'message': 'El término de búsqueda no puede estar vacío',
            'results': []
        })
    
    # Configurar la búsqueda en español
    search_query = SearchQuery(search_string, config='spanish')
    
    # Construir queries para búsqueda en texto
    name_queries = Q()
    for term in search_terms:
        name_queries |= Q(name__icontains=term)
    
    parent_name_queries = Q()
    for term in search_terms:
        parent_name_queries |= Q(parent_drive_file_id__name__icontains=term)
    
    # Búsqueda principal con anotación de ranking
    files = GoogleDriveFile.objects.filter(
        Q(name_queries) |
        Q(parent_name_queries) |
        Q(document__search_vector=search_query) |
        Q(document__description_vector=search_query)
    ).distinct().select_related('parent_drive_file_id', 'document', 'area').annotate(
        # 1) Ranking para coincidencia EXACTA (mayor prioridad)
        exact_name_rank=Case(
            When(name__iexact=search_string, then=Value(100.0)),
            When(name__istartswith=search_string, then=Value(50.0)),
            When(name__icontains=search_string, then=Value(25.0)),
            default=Value(0.0),
            output_field=FloatField()
        ),
        exact_parent_rank=Case(
            When(parent_drive_file_id__name__iexact=search_string, then=Value(80.0)),
            When(parent_drive_file_id__name__istartswith=search_string, then=Value(40.0)),
            When(parent_drive_file_id__name__icontains=search_string, then=Value(20.0)),
            default=Value(0.0),
            output_field=FloatField()
        ),
        # 2) Ranking para búsqueda por términos separados (prioridad media)
        name_rank=SearchRank(
            SearchVector('name', config='spanish'), 
            search_query
        ),
        parent_rank=SearchRank(
            SearchVector('parent_drive_file_id__name', config='spanish'), 
            search_query
        ),
        search_vector_rank=SearchRank(
            F('document__search_vector'), 
            search_query
        ),
        description_rank=SearchRank(
            F('document__description_vector'), 
            search_query
        ),
        # Ranking total ponderado: exacto tiene mayor peso
        total_rank=(
            # Peso alto para coincidencias exactas
            Coalesce('exact_name_rank', Value(0.0, output_field=FloatField())) + 
            Coalesce('exact_parent_rank', Value(0.0, output_field=FloatField())) +
            # Peso medio para búsqueda por términos
            (Coalesce('name_rank', Value(0.0, output_field=FloatField())) * 0.5) + 
            (Coalesce('parent_rank', Value(0.0, output_field=FloatField())) * 0.3) + 
            (Coalesce('search_vector_rank', Value(0.0, output_field=FloatField())) * 0.5) + 
            (Coalesce('description_rank', Value(0.0, output_field=FloatField())) * 0.3)
        )
    ).order_by('-total_rank')
    
    # Función para obtener la jerarquía completa de carpetas padres
    def get_full_hierarchy(file_obj):
        """
        Obtiene la jerarquía completa de carpetas padres
        Retorna una lista de diccionarios con la información de cada nivel
        """
        hierarchy = []
        current = file_obj.parent_drive_file_id
        
        while current:
            hierarchy.insert(0, {
                'drive_file_id': current.drive_file_id,
                'name': current.name,
                'mime_type': current.mime_type,
            })
            current = current.parent_drive_file_id
        
        return hierarchy
    
    # Función para obtener la ruta completa como string
    def get_full_path(file_obj):
        """
        Obtiene la ruta completa como string separada por > 
        Ejemplo: "Raiz > Proyecto > Subcarpeta > Archivo"
        """
        hierarchy = get_full_hierarchy(file_obj)
        path_parts = [item['name'] for item in hierarchy]
        if file_obj.name:
            path_parts.append(file_obj.name)
        return ' > '.join(path_parts)
    
    # Función auxiliar para extraer coincidencias
    def extract_matches(text, terms, exact_string=None):
        """
        Extrae fragmentos de texto que coinciden con los términos de búsqueda
        Prioriza coincidencias exactas
        """
        if not text:
            return []
        
        text_lower = text.lower()
        matches = []
        processed_positions = set()
        
        # 1) PRIMERO buscar coincidencias EXACTAS (prioridad máxima)
        if exact_string:
            exact_lower = exact_string.lower()
            start = 0
            while True:
                pos = text_lower.find(exact_lower, start)
                if pos == -1:
                    break
                
                if pos not in processed_positions:
                    context_start = max(0, pos - 30)
                    context_end = min(len(text), pos + len(exact_string) + 30)
                    fragment = text[context_start:context_end]
                    
                    matches.append({
                        'term': exact_string,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': f"**{text[pos:pos+len(exact_string)]}**",
                        'length': len(exact_string),
                        'match_type': 'exact',
                        'field': 'text_content'  # Para identificar el campo
                    })
                    processed_positions.add(pos)
                
                start = pos + 1
        
        # 2) LUEGO buscar por términos separados (prioridad media)
        for term in terms:
            if term == exact_string:  # Saltar si ya se buscó como exacto
                continue
                
            term_lower = term.lower()
            start = 0
            while True:
                pos = text_lower.find(term_lower, start)
                if pos == -1:
                    break
                
                # Verificar que no sea parte de una coincidencia exacta ya encontrada
                is_duplicate = False
                for processed_pos in processed_positions:
                    if abs(pos - processed_pos) < len(exact_string) if exact_string else False:
                        is_duplicate = True
                        break
                
                if not is_duplicate and pos not in processed_positions:
                    context_start = max(0, pos - 30)
                    context_end = min(len(text), pos + len(term) + 30)
                    fragment = text[context_start:context_end]
                    
                    matches.append({
                        'term': term,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': f"**{text[pos:pos+len(term)]}**",
                        'length': len(term),
                        'match_type': 'term',
                        'field': 'text_content'  # Para identificar el campo
                    })
                    processed_positions.add(pos)
                
                start = pos + 1
        
        # Ordenar por posición y prioridad
        matches.sort(key=lambda x: (x['position'], 0 if x['match_type'] == 'exact' else 1))
        
        return matches
    
    def extract_all_matches(file, terms, exact_string):
        """
        Extrae coincidencias de todos los campos del archivo
        Ahora incluye búsqueda en text_content y description completos
        """
        all_matches = {
            'name': [],
            'parent_name': [],
            'text_content': [],
            'description': []
        }
        
        # Extraer del nombre
        if file.name:
            all_matches['name'] = extract_matches(file.name, terms, exact_string)
            # Actualizar el campo para cada match
            for match in all_matches['name']:
                match['field'] = 'name'
        
        # Extraer del nombre del padre
        if file.parent_drive_file_id and file.parent_drive_file_id.name:
            all_matches['parent_name'] = extract_matches(file.parent_drive_file_id.name, terms, exact_string)
            for match in all_matches['parent_name']:
                match['field'] = 'parent_name'
        
        # Extraer del contenido de texto COMPLETO (no solo preview)
        if hasattr(file, 'document') and file.document and file.document.text_content:
            # Usar todo el texto, no solo preview
            full_text = file.document.text_content
            all_matches['text_content'] = extract_matches(full_text, terms, exact_string)
            for match in all_matches['text_content']:
                match['field'] = 'text_content'
        
        # Extraer de la descripción COMPLETA
        if hasattr(file, 'document') and file.document and file.document.description:
            full_description = file.document.description
            all_matches['description'] = extract_matches(full_description, terms, exact_string)
            for match in all_matches['description']:
                match['field'] = 'description'
        
        return all_matches
    
    # Función para verificar si hay coincidencias en search_vector
    def has_search_vector_match(file, search_query):
        """
        Verifica si el archivo tiene coincidencias en search_vector
        """
        if not hasattr(file, 'document') or not file.document:
            return False
        return GoogleDriveFileDocument.objects.filter(
            file=file, 
            search_vector=search_query
        ).exists()
    
    # Función para verificar si hay coincidencias en description_vector
    def has_description_vector_match(file, search_query):
        """
        Verifica si el archivo tiene coincidencias en description_vector
        """
        if not hasattr(file, 'document') or not file.document:
            return False
        return GoogleDriveFileDocument.objects.filter(
            file=file, 
            description_vector=search_query
        ).exists()
    
    # Construir resultados
    results = []
    for file in files:
        matches = []
        matched_texts = extract_all_matches(file, search_terms, search_string)
        
        # Obtener jerarquía completa
        hierarchy = get_full_hierarchy(file)
        full_path = get_full_path(file)
        
        # Determinar en qué campos se encontraron coincidencias
        # 1) Verificar coincidencias EXACTAS primero
        if any(match['match_type'] == 'exact' for match in matched_texts.get('name', [])):
            matches.append('name_exact')
        elif any(term.lower() in file.name.lower() for term in search_terms):
            matches.append('name')
        
        if file.parent_drive_file_id:
            if any(match['match_type'] == 'exact' for match in matched_texts.get('parent_name', [])):
                matches.append('parent_name_exact')
            elif any(term.lower() in file.parent_drive_file_id.name.lower() for term in search_terms):
                matches.append('parent_name')
        
        # Verificar coincidencias en text_content y description
        if hasattr(file, 'document') and file.document:
            # Coincidencias en text_content
            if any(match['match_type'] == 'exact' for match in matched_texts.get('text_content', [])):
                matches.append('text_content_exact')
            elif has_search_vector_match(file, search_query):
                matches.append('search_vector')
            
            # Coincidencias en description
            if any(match['match_type'] == 'exact' for match in matched_texts.get('description', [])):
                matches.append('description_exact')
            elif has_description_vector_match(file, search_query):
                matches.append('description_vector')
        
        # Contar coincidencias exactas vs términos
        exact_matches = sum(1 for field_matches in matched_texts.values() 
                          for m in field_matches if m.get('match_type') == 'exact')
        term_matches = sum(1 for field_matches in matched_texts.values() 
                         for m in field_matches if m.get('match_type') == 'term')
        
        # Construir el resultado con los textos coincidentes
        result = {
            'id': str(file.id),
            'drive_file_id': file.drive_file_id,
            'name': file.name,
            'mime_type': file.mime_type,
            # Jerarquía completa
            'hierarchy': hierarchy,
            'full_path': full_path,
            'parent_drive_file_id': file.parent_drive_file_id.drive_file_id if file.parent_drive_file_id else None,
            'parent_name': file.parent_drive_file_id.name if file.parent_drive_file_id else None,
            'drive_web_view_link': file.drive_web_view_link,
            'last_known_modified_time': file.last_known_modified_time.isoformat() if file.last_known_modified_time else None,
            'last_synced_at': file.last_synced_at.isoformat() if file.last_synced_at else None,
            'relevance_score': float(file.total_rank) if file.total_rank else 0,
            'relevance_details': {
                'exact_name_rank': float(file.exact_name_rank) if file.exact_name_rank else 0,
                'exact_parent_rank': float(file.exact_parent_rank) if file.exact_parent_rank else 0,
                'name_rank': float(file.name_rank) if file.name_rank else 0,
                'parent_rank': float(file.parent_rank) if file.parent_rank else 0,
                'search_vector_rank': float(file.search_vector_rank) if file.search_vector_rank else 0,
                'description_rank': float(file.description_rank) if file.description_rank else 0,
            },
            'matches_found_in': matches,
            'matched_texts': {
                'total_matches': sum(len(v) for v in matched_texts.values()),
                'exact_matches': exact_matches,
                'term_matches': term_matches,
                'by_field': {
                    field: {
                        'count': len(items),
                        'items': items[:10],  # Limitar a 10 coincidencias por campo
                        'exact_count': sum(1 for m in items if m.get('match_type') == 'exact'),
                        'term_count': sum(1 for m in items if m.get('match_type') == 'term')
                    }
                    for field, items in matched_texts.items() if items
                },
                'summary': {
                    field: {
                        'exact_terms': list(set(item['term'] for item in items if item.get('match_type') == 'exact')),
                        'terms': list(set(item['term'] for item in items if item.get('match_type') == 'term'))
                    }
                    for field, items in matched_texts.items() if items
                }
            },
            'area': file.area_id if file.area else None,
            'area_name': file.area.nombre if file.area else None,
        }
        
        # Información del documento
        if hasattr(file, 'document') and file.document:
            result['document'] = {
                'text_content_preview': file.document.text_content[:500] if file.document.text_content else None,
                'description': file.document.description,
            }
        
        results.append(result)
    
    return JsonResponse({
        'status': 'success',
        'search_string': search_string,
        'search_terms': search_terms,
        'total_results': len(results),
        'results': results
    }, json_dumps_params={'ensure_ascii': False})


from django.db.models import Q, F, Value, FloatField, Case, When
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models.functions import Coalesce
from django.http import JsonResponse
import unicodedata
import re

def search_google_drive_files_ranked_v3(search_string):
    """
    Búsqueda con ranking de relevancia y extracción de textos coincidentes
    1) Primero busca exactamente el string ingresado y da el ranking mayor
    2) Luego usa search_string.split() para búsqueda más amplia
    """
    search_terms = search_string.strip().split()
    
    if not search_terms:
        return JsonResponse({
            'status': 'error',
            'message': 'El término de búsqueda no puede estar vacío',
            'results': []
        })
    
    # Configurar la búsqueda en español
    search_query = SearchQuery(search_string, config='spanish')
    
    # Construir queries para búsqueda en texto
    name_queries = Q()
    for term in search_terms:
        name_queries |= Q(name__icontains=term)
    
    parent_name_queries = Q()
    for term in search_terms:
        parent_name_queries |= Q(parent_drive_file_id__name__icontains=term)
    
    # Búsqueda principal con anotación de ranking
    files = GoogleDriveFile.objects.filter(
        Q(name_queries) |
        Q(parent_name_queries) |
        Q(document__search_vector=search_query) |
        Q(document__description_vector=search_query)
    ).distinct().select_related('parent_drive_file_id', 'document', 'area').annotate(
        # 1) Ranking para coincidencia EXACTA (mayor prioridad)
        exact_name_rank=Case(
            When(name__iexact=search_string, then=Value(100.0)),
            When(name__istartswith=search_string, then=Value(50.0)),
            When(name__icontains=search_string, then=Value(25.0)),
            default=Value(0.0),
            output_field=FloatField()
        ),
        exact_parent_rank=Case(
            When(parent_drive_file_id__name__iexact=search_string, then=Value(80.0)),
            When(parent_drive_file_id__name__istartswith=search_string, then=Value(40.0)),
            When(parent_drive_file_id__name__icontains=search_string, then=Value(20.0)),
            default=Value(0.0),
            output_field=FloatField()
        ),
        # 2) Ranking para búsqueda por términos separados (prioridad media)
        name_rank=SearchRank(
            SearchVector('name', config='spanish'), 
            search_query
        ),
        parent_rank=SearchRank(
            SearchVector('parent_drive_file_id__name', config='spanish'), 
            search_query
        ),
        search_vector_rank=SearchRank(
            F('document__search_vector'), 
            search_query
        ),
        description_rank=SearchRank(
            F('document__description_vector'), 
            search_query
        ),
        # Ranking total ponderado: exacto tiene mayor peso
        total_rank=(
            # Peso alto para coincidencias exactas
            Coalesce('exact_name_rank', Value(0.0, output_field=FloatField())) + 
            Coalesce('exact_parent_rank', Value(0.0, output_field=FloatField())) +
            # Peso medio para búsqueda por términos
            (Coalesce('name_rank', Value(0.0, output_field=FloatField())) * 0.5) + 
            (Coalesce('parent_rank', Value(0.0, output_field=FloatField())) * 0.3) + 
            (Coalesce('search_vector_rank', Value(0.0, output_field=FloatField())) * 0.5) + 
            (Coalesce('description_rank', Value(0.0, output_field=FloatField())) * 0.3)
        )
    ).order_by('-total_rank')
    
    # Función para normalizar texto (como lo hace PostgreSQL con unaccent + stemming)
    def normalize_text(text):
        """
        Normaliza el texto para búsqueda:
        - Elimina acentos
        - Convierte a minúsculas
        - Elimina caracteres especiales
        """
        if not text:
            return ""
        # Convertir a minúsculas
        text = text.lower()
        # Eliminar acentos
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
        # Eliminar caracteres especiales (opcional, depende del config de PostgreSQL)
        text = re.sub(r'[^\w\s]', ' ', text)
        # Reducir espacios múltiples
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    # Función para obtener la jerarquía completa de carpetas padres
    def get_full_hierarchy(file_obj):
        """
        Obtiene la jerarquía completa de carpetas padres
        Retorna una lista de diccionarios con la información de cada nivel
        """
        hierarchy = []
        current = file_obj.parent_drive_file_id
        
        while current:
            hierarchy.insert(0, {
                'drive_file_id': current.drive_file_id,
                'name': current.name,
                'mime_type': current.mime_type,
            })
            current = current.parent_drive_file_id
        
        return hierarchy
    
    # Función para obtener la ruta completa como string
    def get_full_path(file_obj):
        """
        Obtiene la ruta completa como string separada por > 
        Ejemplo: "Raiz > Proyecto > Subcarpeta > Archivo"
        """
        hierarchy = get_full_hierarchy(file_obj)
        path_parts = [item['name'] for item in hierarchy]
        if file_obj.name:
            path_parts.append(file_obj.name)
        return ' > '.join(path_parts)
    
    # Función auxiliar para extraer coincidencias (USANDO NORMALIZACIÓN)
    def extract_matches(text, terms, exact_string=None):
        """
        Extrae fragmentos de texto que coinciden con los términos de búsqueda
        Usa normalización para encontrar coincidencias como en search_vector
        """
        if not text:
            return []
        
        # Texto normalizado para buscar
        text_normalized = normalize_text(text)
        matches = []
        processed_positions = set()
        
        # 1) PRIMERO buscar coincidencias EXACTAS (prioridad máxima)
        if exact_string:
            exact_normalized = normalize_text(exact_string)
            start = 0
            while True:
                pos = text_normalized.find(exact_normalized, start)
                if pos == -1:
                    break
                
                if pos not in processed_positions:
                    context_start = max(0, pos - 30)
                    context_end = min(len(text), pos + len(exact_string) + 30)
                    fragment = text[context_start:context_end]
                    
                    # Buscar el texto original que coincide
                    # Intentamos encontrar la coincidencia en el texto original
                    original_fragment = text[context_start:context_end]
                    
                    matches.append({
                        'term': exact_string,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': f"**{exact_string}**",
                        'length': len(exact_string),
                        'match_type': 'exact',
                        'field': 'text_content'
                    })
                    processed_positions.add(pos)
                
                start = pos + 1
        
        # 2) LUEGO buscar por términos separados (prioridad media)
        for term in terms:
            if term == exact_string:  # Saltar si ya se buscó como exacto
                continue
            
            term_normalized = normalize_text(term)
            start = 0
            while True:
                pos = text_normalized.find(term_normalized, start)
                if pos == -1:
                    break
                
                # Verificar que no sea parte de una coincidencia exacta ya encontrada
                is_duplicate = False
                for processed_pos in processed_positions:
                    if abs(pos - processed_pos) < len(exact_string) if exact_string else False:
                        is_duplicate = True
                        break
                
                if not is_duplicate and pos not in processed_positions:
                    context_start = max(0, pos - 30)
                    context_end = min(len(text), pos + len(term) + 30)
                    fragment = text[context_start:context_end]
                    
                    matches.append({
                        'term': term,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': f"**{term}**",
                        'length': len(term),
                        'match_type': 'term',
                        'field': 'text_content'
                    })
                    processed_positions.add(pos)
                
                start = pos + 1
        
        # Ordenar por posición y prioridad
        matches.sort(key=lambda x: (x['position'], 0 if x['match_type'] == 'exact' else 1))
        
        return matches
    
    def extract_all_matches(file, terms, exact_string):
        """
        Extrae coincidencias de todos los campos del archivo
        """
        all_matches = {
            'name': [],
            'parent_name': [],
            'text_content': [],
            'description': []
        }
        
        # Extraer del nombre
        if file.name:
            all_matches['name'] = extract_matches(file.name, terms, exact_string)
            for match in all_matches['name']:
                match['field'] = 'name'
        
        # Extraer del nombre del padre
        if file.parent_drive_file_id and file.parent_drive_file_id.name:
            all_matches['parent_name'] = extract_matches(file.parent_drive_file_id.name, terms, exact_string)
            for match in all_matches['parent_name']:
                match['field'] = 'parent_name'
        
        # Extraer del contenido de texto COMPLETO
        if hasattr(file, 'document') and file.document and file.document.text_content:
            full_text = file.document.text_content
            all_matches['text_content'] = extract_matches(full_text, terms, exact_string)
            for match in all_matches['text_content']:
                match['field'] = 'text_content'
        
        # Extraer de la descripción COMPLETA
        if hasattr(file, 'document') and file.document and file.document.description:
            full_description = file.document.description
            all_matches['description'] = extract_matches(full_description, terms, exact_string)
            for match in all_matches['description']:
                match['field'] = 'description'
        
        return all_matches
    
    # Función para verificar si hay coincidencias en search_vector
    def has_search_vector_match(file, search_query):
        """
        Verifica si el archivo tiene coincidencias en search_vector
        """
        if not hasattr(file, 'document') or not file.document:
            return False
        return GoogleDriveFileDocument.objects.filter(
            file=file, 
            search_vector=search_query
        ).exists()
    
    # Función para verificar si hay coincidencias en description_vector
    def has_description_vector_match(file, search_query):
        """
        Verifica si el archivo tiene coincidencias en description_vector
        """
        if not hasattr(file, 'document') or not file.document:
            return False
        return GoogleDriveFileDocument.objects.filter(
            file=file, 
            description_vector=search_query
        ).exists()
    
    # Función para verificar si un archivo tiene ALGUNA coincidencia de texto
    def has_any_text_match(file, matched_texts):
        """
        Verifica si el archivo tiene al menos una coincidencia en algún campo
        """
        total_matches = sum(len(matches) for matches in matched_texts.values())
        return total_matches > 0
    
    # Construir resultados
    results = []
    for file in files:
        matched_texts = extract_all_matches(file, search_terms, search_string)
        
        # SOLO incluir archivos que tengan AL MENOS UNA coincidencia de texto
        if not has_any_text_match(file, matched_texts):
            continue  # Saltar este archivo
        
        matches = []
        
        # Obtener jerarquía completa
        hierarchy = get_full_hierarchy(file)
        full_path = get_full_path(file)
        
        # Determinar en qué campos se encontraron coincidencias
        if any(match['match_type'] == 'exact' for match in matched_texts.get('name', [])):
            matches.append('name_exact')
        elif any(term.lower() in file.name.lower() for term in search_terms):
            matches.append('name')
        
        if file.parent_drive_file_id:
            if any(match['match_type'] == 'exact' for match in matched_texts.get('parent_name', [])):
                matches.append('parent_name_exact')
            elif any(term.lower() in file.parent_drive_file_id.name.lower() for term in search_terms):
                matches.append('parent_name')
        
        if hasattr(file, 'document') and file.document:
            if any(match['match_type'] == 'exact' for match in matched_texts.get('text_content', [])):
                matches.append('text_content_exact')
            elif has_search_vector_match(file, search_query):
                matches.append('search_vector')
            
            if any(match['match_type'] == 'exact' for match in matched_texts.get('description', [])):
                matches.append('description_exact')
            elif has_description_vector_match(file, search_query):
                matches.append('description_vector')
        
        # Contar coincidencias exactas vs términos
        exact_matches = sum(1 for field_matches in matched_texts.values() 
                          for m in field_matches if m.get('match_type') == 'exact')
        term_matches = sum(1 for field_matches in matched_texts.values() 
                         for m in field_matches if m.get('match_type') == 'term')
        
        # Construir el resultado
        result = {
            'id': str(file.id),
            'drive_file_id': file.drive_file_id,
            'name': file.name,
            'mime_type': file.mime_type,
            'hierarchy': hierarchy,
            'full_path': full_path,
            'parent_drive_file_id': file.parent_drive_file_id.drive_file_id if file.parent_drive_file_id else None,
            'parent_name': file.parent_drive_file_id.name if file.parent_drive_file_id else None,
            'drive_web_view_link': file.drive_web_view_link,
            'last_known_modified_time': file.last_known_modified_time.isoformat() if file.last_known_modified_time else None,
            'last_synced_at': file.last_synced_at.isoformat() if file.last_synced_at else None,
            'relevance_score': float(file.total_rank) if file.total_rank else 0,
            'relevance_details': {
                'exact_name_rank': float(file.exact_name_rank) if file.exact_name_rank else 0,
                'exact_parent_rank': float(file.exact_parent_rank) if file.exact_parent_rank else 0,
                'name_rank': float(file.name_rank) if file.name_rank else 0,
                'parent_rank': float(file.parent_rank) if file.parent_rank else 0,
                'search_vector_rank': float(file.search_vector_rank) if file.search_vector_rank else 0,
                'description_rank': float(file.description_rank) if file.description_rank else 0,
            },
            'matches_found_in': matches,
            'matched_texts': {
                'total_matches': sum(len(v) for v in matched_texts.values()),
                'exact_matches': exact_matches,
                'term_matches': term_matches,
                'by_field': {
                    field: {
                        'count': len(items),
                        'items': items[:10],
                        'exact_count': sum(1 for m in items if m.get('match_type') == 'exact'),
                        'term_count': sum(1 for m in items if m.get('match_type') == 'term')
                    }
                    for field, items in matched_texts.items() if items
                },
                'summary': {
                    field: {
                        'exact_terms': list(set(item['term'] for item in items if item.get('match_type') == 'exact')),
                        'terms': list(set(item['term'] for item in items if item.get('match_type') == 'term'))
                    }
                    for field, items in matched_texts.items() if items
                }
            },
            'area': file.area_id if file.area else None,
            'area_name': file.area.nombre if file.area else None,
        }
        
        # Información del documento
        if hasattr(file, 'document') and file.document:
            result['document'] = {
                'text_content_preview': file.document.text_content[:500] if file.document.text_content else None,
                'description': file.document.description,
            }
        
        results.append(result)
    
    return JsonResponse({
        'status': 'success',
        'search_string': search_string,
        'search_terms': search_terms,
        'total_results': len(results),
        'results': results
    }, json_dumps_params={'ensure_ascii': False})

from django.db.models import Q, F, Value, FloatField, Case, When
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models.functions import Coalesce
from django.http import JsonResponse
import unicodedata
import re

def search_google_drive_files_ranked_v4(search_string):
    """
    Búsqueda con ranking de relevancia y extracción de textos coincidentes
    1) Primero busca exactamente el string ingresado y da el ranking mayor
    2) Luego usa search_string.split() para búsqueda más amplia
    Busca palabras completas usando word boundaries (\\b)
    """
    # Dividir la búsqueda en términos y filtrar palabras de menos de 3 caracteres
    raw_terms = search_string.strip().split()
    # Filtrar palabras con menos de 3 caracteres (excluir "a", "de", "los", etc.)
    search_terms = [term for term in raw_terms if len(term) >= 3]
    
    if not search_terms:
        return JsonResponse({
            'status': 'error',
            'message': 'El término de búsqueda debe tener al menos 3 caracteres',
            'results': []
        })
    
    # Configurar la búsqueda en español
    search_query = SearchQuery(search_string, config='spanish')
    
    # Construir queries para búsqueda en texto
    name_queries = Q()
    for term in search_terms:
        name_queries |= Q(name__icontains=term)
    
    parent_name_queries = Q()
    for term in search_terms:
        parent_name_queries |= Q(parent_drive_file_id__name__icontains=term)
    
    # Búsqueda principal con anotación de ranking
    files = GoogleDriveFile.objects.filter(
        Q(name_queries) |
        Q(parent_name_queries) |
        Q(document__search_vector=search_query) |
        Q(document__description_vector=search_query)
    ).distinct().select_related('parent_drive_file_id', 'document', 'area').annotate(
        # 1) Ranking para coincidencia EXACTA (mayor prioridad)
        exact_name_rank=Case(
            When(name__iexact=search_string, then=Value(100.0)),
            When(name__istartswith=search_string, then=Value(50.0)),
            When(name__icontains=search_string, then=Value(25.0)),
            default=Value(0.0),
            output_field=FloatField()
        ),
        exact_parent_rank=Case(
            When(parent_drive_file_id__name__iexact=search_string, then=Value(80.0)),
            When(parent_drive_file_id__name__istartswith=search_string, then=Value(40.0)),
            When(parent_drive_file_id__name__icontains=search_string, then=Value(20.0)),
            default=Value(0.0),
            output_field=FloatField()
        ),
        # 2) Ranking para búsqueda por términos separados (prioridad media)
        name_rank=SearchRank(
            SearchVector('name', config='spanish'), 
            search_query
        ),
        parent_rank=SearchRank(
            SearchVector('parent_drive_file_id__name', config='spanish'), 
            search_query
        ),
        search_vector_rank=SearchRank(
            F('document__search_vector'), 
            search_query
        ),
        description_rank=SearchRank(
            F('document__description_vector'), 
            search_query
        ),
        # Ranking total ponderado: exacto tiene mayor peso
        total_rank=(
            # Peso alto para coincidencias exactas
            Coalesce('exact_name_rank', Value(0.0, output_field=FloatField())) + 
            Coalesce('exact_parent_rank', Value(0.0, output_field=FloatField())) +
            # Peso medio para búsqueda por términos
            (Coalesce('name_rank', Value(0.0, output_field=FloatField())) * 0.5) + 
            (Coalesce('parent_rank', Value(0.0, output_field=FloatField())) * 0.3) + 
            (Coalesce('search_vector_rank', Value(0.0, output_field=FloatField())) * 0.5) + 
            (Coalesce('description_rank', Value(0.0, output_field=FloatField())) * 0.3)
        )
    ).order_by('-total_rank')
    
    # Función para normalizar texto (como lo hace PostgreSQL con unaccent + stemming)
    def normalize_text(text):
        """
        Normaliza el texto para búsqueda:
        - Elimina acentos
        - Convierte a minúsculas
        - Elimina caracteres especiales
        """
        if not text:
            return ""
        # Convertir a minúsculas
        text = text.lower()
        # Eliminar acentos
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
        # Eliminar caracteres especiales pero mantener palabras
        text = re.sub(r'[^\w\s]', ' ', text)
        # Reducir espacios múltiples
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    # Función para verificar si una palabra existe como palabra completa en un texto
    def has_word_match(text, term):
        """
        Verifica si un término existe como palabra completa en el texto
        """
        if not text or not term:
            return False
        
        text_normalized = normalize_text(text)
        term_normalized = normalize_text(term)
        pattern = r'\b' + re.escape(term_normalized) + r'\b'
        return bool(re.search(pattern, text_normalized))
    
    # Función para obtener la jerarquía completa de carpetas padres
    def get_full_hierarchy(file_obj):
        """
        Obtiene la jerarquía completa de carpetas padres
        Retorna una lista de diccionarios con la información de cada nivel
        """
        hierarchy = []
        current = file_obj.parent_drive_file_id
        
        while current:
            hierarchy.insert(0, {
                'drive_file_id': current.drive_file_id,
                'name': current.name,
                'mime_type': current.mime_type,
            })
            current = current.parent_drive_file_id
        
        return hierarchy
    
    # Función para obtener la ruta completa como string
    def get_full_path(file_obj):
        """
        Obtiene la ruta completa como string separada por > 
        Ejemplo: "Raiz > Proyecto > Subcarpeta > Archivo"
        """
        hierarchy = get_full_hierarchy(file_obj)
        path_parts = [item['name'] for item in hierarchy]
        if file_obj.name:
            path_parts.append(file_obj.name)
        return ' > '.join(path_parts)
    
    # Función auxiliar para extraer coincidencias de PALABRAS COMPLETAS
    def extract_matches(text, terms, exact_string=None):
        """
        Extrae fragmentos de texto que coinciden con los términos de búsqueda
        Usa word boundaries (\\b) para encontrar palabras completas
        """
        if not text:
            return []
        
        # Texto normalizado para buscar
        text_normalized = normalize_text(text)
        matches = []
        processed_positions = set()
        
        # 1) PRIMERO buscar coincidencias EXACTAS (prioridad máxima)
        if exact_string:
            exact_normalized = normalize_text(exact_string)
            # Buscar como palabra completa usando word boundaries
            pattern = r'\b' + re.escape(exact_normalized) + r'\b'
            for match in re.finditer(pattern, text_normalized):
                pos = match.start()
                if pos not in processed_positions:
                    context_start = max(0, pos - 20)
                    context_end = min(len(text), pos + len(exact_string) + 30)
                    fragment = text[context_start:context_end]
                    
                    matches.append({
                        'term': exact_string,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': f"**{exact_string}**",
                        'length': len(exact_string),
                        'match_type': 'exact',
                        'field': 'text_content'
                    })
                    processed_positions.add(pos)
        
        # 2) LUEGO buscar por términos separados (prioridad media)
        for term in terms:
            if term == exact_string:  # Saltar si ya se buscó como exacto
                continue
            
            term_normalized = normalize_text(term)
            # Buscar como palabra completa usando word boundaries
            pattern = r'\b' + re.escape(term_normalized) + r'\b'
            for match in re.finditer(pattern, text_normalized):
                pos = match.start()
                
                # Verificar que no sea parte de una coincidencia exacta ya encontrada
                is_duplicate = False
                for processed_pos in processed_positions:
                    if abs(pos - processed_pos) < len(exact_string) if exact_string else False:
                        is_duplicate = True
                        break
                
                if not is_duplicate and pos not in processed_positions:
                    context_start = max(0, pos - 30)
                    context_end = min(len(text), pos + len(term) + 30)
                    fragment = text[context_start:context_end]
                    
                    matches.append({
                        'term': term,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': f"**{term}**",
                        'length': len(term),
                        'match_type': 'term',
                        'field': 'text_content'
                    })
                    processed_positions.add(pos)
        
        # Ordenar por posición y prioridad
        matches.sort(key=lambda x: (x['position'], 0 if x['match_type'] == 'exact' else 1))
        
        return matches
    
    def extract_all_matches(file, terms, exact_string):
        """
        Extrae coincidencias de todos los campos del archivo
        """
        all_matches = {
            'name': [],
            'parent_name': [],
            'text_content': [],
            'description': []
        }
        
        # Extraer del nombre
        if file.name:
            all_matches['name'] = extract_matches(file.name, terms, exact_string)
            for match in all_matches['name']:
                match['field'] = 'name'
        
        # Extraer del nombre del padre
        if file.parent_drive_file_id and file.parent_drive_file_id.name:
            all_matches['parent_name'] = extract_matches(file.parent_drive_file_id.name, terms, exact_string)
            for match in all_matches['parent_name']:
                match['field'] = 'parent_name'
        
        # Extraer del contenido de texto COMPLETO
        if hasattr(file, 'document') and file.document and file.document.text_content:
            full_text = file.document.text_content
            all_matches['text_content'] = extract_matches(full_text, terms, exact_string)
            for match in all_matches['text_content']:
                match['field'] = 'text_content'
        
        # Extraer de la descripción COMPLETA
        if hasattr(file, 'document') and file.document and file.document.description:
            full_description = file.document.description
            all_matches['description'] = extract_matches(full_description, terms, exact_string)
            for match in all_matches['description']:
                match['field'] = 'description'
        
        return all_matches
    
    # Función para verificar si hay coincidencias en search_vector
    def has_search_vector_match(file, search_query):
        """
        Verifica si el archivo tiene coincidencias en search_vector
        """
        if not hasattr(file, 'document') or not file.document:
            return False
        return GoogleDriveFileDocument.objects.filter(
            file=file, 
            search_vector=search_query
        ).exists()
    
    # Función para verificar si hay coincidencias en description_vector
    def has_description_vector_match(file, search_query):
        """
        Verifica si el archivo tiene coincidencias en description_vector
        """
        if not hasattr(file, 'document') or not file.document:
            return False
        return GoogleDriveFileDocument.objects.filter(
            file=file, 
            description_vector=search_query
        ).exists()
    
    # Función para verificar si un archivo tiene ALGUNA coincidencia de texto
    def has_any_text_match(file, matched_texts):
        """
        Verifica si el archivo tiene al menos una coincidencia en algún campo
        """
        total_matches = sum(len(matches) for matches in matched_texts.values())
        return total_matches > 0
    
    # Construir resultados
    results = []
    for file in files:
        matched_texts = extract_all_matches(file, search_terms, search_string)
        
        # SOLO incluir archivos que tengan AL MENOS UNA coincidencia de texto
        if not has_any_text_match(file, matched_texts):
            continue  # Saltar este archivo
        
        matches_found = []
        
        # Obtener jerarquía completa
        hierarchy = get_full_hierarchy(file)
        full_path = get_full_path(file)
        
        # Determinar en qué campos se encontraron coincidencias
        # Usando word boundaries para verificar coincidencias de palabras completas
        
        # Verificar coincidencias en name
        if any(match['match_type'] == 'exact' for match in matched_texts.get('name', [])):
            matches_found.append('name_exact')
        elif any(has_word_match(file.name, term) for term in search_terms):
            matches_found.append('name')
        
        # Verificar coincidencias en parent_name
        if file.parent_drive_file_id:
            if any(match['match_type'] == 'exact' for match in matched_texts.get('parent_name', [])):
                matches_found.append('parent_name_exact')
            elif any(has_word_match(file.parent_drive_file_id.name, term) for term in search_terms):
                matches_found.append('parent_name')
        
        # Verificar coincidencias en text_content y description
        if hasattr(file, 'document') and file.document:
            # Coincidencias en text_content
            if any(match['match_type'] == 'exact' for match in matched_texts.get('text_content', [])):
                matches_found.append('text_content_exact')
            elif has_search_vector_match(file, search_query):
                matches_found.append('search_vector')
            
            # Coincidencias en description
            if any(match['match_type'] == 'exact' for match in matched_texts.get('description', [])):
                matches_found.append('description_exact')
            elif has_description_vector_match(file, search_query):
                matches_found.append('description_vector')
        
        # Contar coincidencias exactas vs términos
        exact_matches = sum(1 for field_matches in matched_texts.values() 
                          for m in field_matches if m.get('match_type') == 'exact')
        term_matches = sum(1 for field_matches in matched_texts.values() 
                         for m in field_matches if m.get('match_type') == 'term')
        
        # Construir el resultado
        result = {
            'id': str(file.id),
            'drive_file_id': file.drive_file_id,
            'name': file.name,
            'mime_type': file.mime_type,
            'hierarchy': hierarchy,
            'full_path': full_path,
            'parent_drive_file_id': file.parent_drive_file_id.drive_file_id if file.parent_drive_file_id else None,
            'parent_name': file.parent_drive_file_id.name if file.parent_drive_file_id else None,
            'drive_web_view_link': file.drive_web_view_link,
            'last_known_modified_time': file.last_known_modified_time.isoformat() if file.last_known_modified_time else None,
            'last_synced_at': file.last_synced_at.isoformat() if file.last_synced_at else None,
            'relevance_score': float(file.total_rank) if file.total_rank else 0,
            'relevance_details': {
                'exact_name_rank': float(file.exact_name_rank) if file.exact_name_rank else 0,
                'exact_parent_rank': float(file.exact_parent_rank) if file.exact_parent_rank else 0,
                'name_rank': float(file.name_rank) if file.name_rank else 0,
                'parent_rank': float(file.parent_rank) if file.parent_rank else 0,
                'search_vector_rank': float(file.search_vector_rank) if file.search_vector_rank else 0,
                'description_rank': float(file.description_rank) if file.description_rank else 0,
            },
            'matches_found_in': matches_found,
            'matched_texts': {
                'total_matches': sum(len(v) for v in matched_texts.values()),
                'exact_matches': exact_matches,
                'term_matches': term_matches,
                'by_field': {
                    field: {
                        'count': len(items),
                        'items': items[:10],
                        'exact_count': sum(1 for m in items if m.get('match_type') == 'exact'),
                        'term_count': sum(1 for m in items if m.get('match_type') == 'term')
                    }
                    for field, items in matched_texts.items() if items
                },
                'summary': {
                    field: {
                        'exact_terms': list(set(item['term'] for item in items if item.get('match_type') == 'exact')),
                        'terms': list(set(item['term'] for item in items if item.get('match_type') == 'term'))
                    }
                    for field, items in matched_texts.items() if items
                }
            },
            'area': file.area_id if file.area else None,
            'area_name': file.area.nombre if file.area else None,
        }
        
        # Información del documento
        if hasattr(file, 'document') and file.document:
            result['document'] = {
                'text_content_preview': file.document.text_content[:500] if file.document.text_content else None,
                'description': file.document.description,
            }
        
        results.append(result)
    
    return JsonResponse({
        'status': 'success',
        'search_string': search_string,
        'search_terms': search_terms,
        'total_results': len(results),
        'results': results
    }, json_dumps_params={'ensure_ascii': False})





from django.db.models import Q, F, Value, FloatField, Case, When
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models.functions import Coalesce
from django.http import JsonResponse
import unicodedata
import re

def search_google_drive_files_ranked_v5(search_string):
    """
    Búsqueda con ranking de relevancia y extracción de textos coincidentes
    1) Primero busca exactamente el string ingresado y da el ranking mayor
    2) Luego usa search_string.split() para búsqueda más amplia
    Busca palabras completas usando word boundaries (\\b)
    """
    # Dividir la búsqueda en términos y filtrar palabras de menos de 3 caracteres
    raw_terms = search_string.strip().split()
    # Filtrar palabras con menos de 3 caracteres (excluir "a", "de", "los", etc.)
    search_terms = [term for term in raw_terms if len(term) >= 3]
    
    if not search_terms:
        return JsonResponse({
            'status': 'error',
            'message': 'El término de búsqueda debe tener al menos 3 caracteres',
            'results': []
        })
    
    # Configurar la búsqueda en español
    search_query = SearchQuery(search_string, config='spanish')
    
    # Construir queries para búsqueda en texto
    name_queries = Q()
    for term in search_terms:
        name_queries |= Q(name__icontains=term)
    
    parent_name_queries = Q()
    for term in search_terms:
        parent_name_queries |= Q(parent_drive_file_id__name__icontains=term)
    
    # Búsqueda principal con anotación de ranking
    files = GoogleDriveFile.objects.filter(
        Q(name_queries) |
        Q(parent_name_queries) |
        Q(document__search_vector=search_query) |
        Q(document__description_vector=search_query)
    ).distinct().select_related('parent_drive_file_id', 'document', 'area').annotate(
        # 1) Ranking para coincidencia EXACTA (mayor prioridad)
        exact_name_rank=Case(
            When(name__iexact=search_string, then=Value(100.0)),
            When(name__istartswith=search_string, then=Value(50.0)),
            When(name__icontains=search_string, then=Value(25.0)),
            default=Value(0.0),
            output_field=FloatField()
        ),
        exact_parent_rank=Case(
            When(parent_drive_file_id__name__iexact=search_string, then=Value(80.0)),
            When(parent_drive_file_id__name__istartswith=search_string, then=Value(40.0)),
            When(parent_drive_file_id__name__icontains=search_string, then=Value(20.0)),
            default=Value(0.0),
            output_field=FloatField()
        ),
        # 2) Ranking para búsqueda por términos separados (prioridad media)
        name_rank=SearchRank(
            SearchVector('name', config='spanish'), 
            search_query
        ),
        parent_rank=SearchRank(
            SearchVector('parent_drive_file_id__name', config='spanish'), 
            search_query
        ),
        search_vector_rank=SearchRank(
            F('document__search_vector'), 
            search_query
        ),
        description_rank=SearchRank(
            F('document__description_vector'), 
            search_query
        ),
        # Ranking total ponderado: exacto tiene mayor peso
        total_rank=(
            # Peso alto para coincidencias exactas
            Coalesce('exact_name_rank', Value(0.0, output_field=FloatField())) + 
            Coalesce('exact_parent_rank', Value(0.0, output_field=FloatField())) +
            # Peso medio para búsqueda por términos
            (Coalesce('name_rank', Value(0.0, output_field=FloatField())) * 0.5) + 
            (Coalesce('parent_rank', Value(0.0, output_field=FloatField())) * 0.3) + 
            (Coalesce('search_vector_rank', Value(0.0, output_field=FloatField())) * 0.5) + 
            (Coalesce('description_rank', Value(0.0, output_field=FloatField())) * 0.3)
        )
    ).order_by('-total_rank')
    
    # Función para normalizar texto (como lo hace PostgreSQL con unaccent + stemming)
    def normalize_text(text):
        """
        Normaliza el texto para búsqueda:
        - Elimina acentos
        - Convierte a minúsculas
        - Elimina caracteres especiales
        """
        if not text:
            return ""
        # Convertir a minúsculas
        text = text.lower()
        # Eliminar acentos
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
        # Eliminar caracteres especiales pero mantener palabras
        text = re.sub(r'[^\w\s]', ' ', text)
        # Reducir espacios múltiples
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    # Función para verificar si una palabra existe como palabra completa en un texto
    def has_word_match(text, term):
        """
        Verifica si un término existe como palabra completa en el texto
        """
        if not text or not term:
            return False
        
        text_normalized = normalize_text(text)
        term_normalized = normalize_text(term)
        pattern = r'\b' + re.escape(term_normalized) + r'\b'
        return bool(re.search(pattern, text_normalized))
    
    # Función para obtener la jerarquía completa de carpetas padres
    def get_full_hierarchy(file_obj):
        """
        Obtiene la jerarquía completa de carpetas padres
        Retorna una lista de diccionarios con la información de cada nivel
        """
        hierarchy = []
        current = file_obj.parent_drive_file_id
        
        while current:
            hierarchy.insert(0, {
                'drive_file_id': current.drive_file_id,
                'name': current.name,
                'mime_type': current.mime_type,
            })
            current = current.parent_drive_file_id
        
        return hierarchy
    
    # Función para obtener la ruta completa como string
    def get_full_path(file_obj):
        """
        Obtiene la ruta completa como string separada por > 
        Ejemplo: "Raiz > Proyecto > Subcarpeta > Archivo"
        """
        hierarchy = get_full_hierarchy(file_obj)
        path_parts = [item['name'] for item in hierarchy]
        if file_obj.name:
            path_parts.append(file_obj.name)
        return ' > '.join(path_parts)
    
    # Función auxiliar para extraer coincidencias de PALABRAS COMPLETAS
    def extract_matches(text, terms, exact_string=None):
        """
        Extrae fragmentos de texto que coinciden con los términos de búsqueda
        Usa word boundaries (\\b) para encontrar palabras completas
        """
        if not text:
            return []
        
        # Texto normalizado para buscar
        text_normalized = normalize_text(text)
        matches = []
        processed_positions = set()
        
        # Configurar tamaño del contexto (más grande para mostrar más texto)
        CONTEXT_SIZE = 80  # Aumentado de 20/30 a 80 caracteres alrededor
        
        # 1) PRIMERO buscar coincidencias EXACTAS (prioridad máxima)
        if exact_string:
            exact_normalized = normalize_text(exact_string)
            # Buscar como palabra completa usando word boundaries
            pattern = r'\b' + re.escape(exact_normalized) + r'\b'
            for match in re.finditer(pattern, text_normalized):
                pos = match.start()
                if pos not in processed_positions:
                    context_start = max(0, pos - CONTEXT_SIZE)
                    context_end = min(len(text), pos + len(exact_string) + CONTEXT_SIZE)
                    fragment = text[context_start:context_end]
                    
                    # Resaltar el término en el contexto
                    highlighted_fragment = fragment.replace(
                        text[pos-context_start:pos-context_start+len(exact_string)],
                        f"**{exact_string}**"
                    ) if pos >= context_start else fragment
                    
                    matches.append({
                        'term': exact_string,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': highlighted_fragment.strip(),
                        'length': len(exact_string),
                        'match_type': 'exact',
                        'field': 'text_content'
                    })
                    processed_positions.add(pos)
        
        # 2) LUEGO buscar por términos separados (prioridad media)
        for term in terms:
            if term == exact_string:  # Saltar si ya se buscó como exacto
                continue
            
            term_normalized = normalize_text(term)
            # Buscar como palabra completa usando word boundaries
            pattern = r'\b' + re.escape(term_normalized) + r'\b'
            for match in re.finditer(pattern, text_normalized):
                pos = match.start()
                
                # Verificar que no sea parte de una coincidencia exacta ya encontrada
                is_duplicate = False
                for processed_pos in processed_positions:
                    if abs(pos - processed_pos) < len(exact_string) if exact_string else False:
                        is_duplicate = True
                        break
                
                if not is_duplicate and pos not in processed_positions:
                    context_start = max(0, pos - CONTEXT_SIZE)
                    context_end = min(len(text), pos + len(term) + CONTEXT_SIZE)
                    fragment = text[context_start:context_end]
                    
                    # Resaltar el término en el contexto
                    highlighted_fragment = fragment.replace(
                        text[pos-context_start:pos-context_start+len(term)],
                        f"**{term}**"
                    ) if pos >= context_start else fragment
                    
                    matches.append({
                        'term': term,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': highlighted_fragment.strip(),
                        'length': len(term),
                        'match_type': 'term',
                        'field': 'text_content'
                    })
                    processed_positions.add(pos)
        
        # Ordenar por posición y prioridad
        matches.sort(key=lambda x: (x['position'], 0 if x['match_type'] == 'exact' else 1))
        
        return matches
    
    def extract_all_matches(file, terms, exact_string):
        """
        Extrae coincidencias de todos los campos del archivo
        """
        all_matches = {
            'name': [],
            'parent_name': [],
            'text_content': [],
            'description': []
        }
        
        # Extraer del nombre
        if file.name:
            all_matches['name'] = extract_matches(file.name, terms, exact_string)
            for match in all_matches['name']:
                match['field'] = 'name'
        
        # Extraer del nombre del padre
        if file.parent_drive_file_id and file.parent_drive_file_id.name:
            all_matches['parent_name'] = extract_matches(file.parent_drive_file_id.name, terms, exact_string)
            for match in all_matches['parent_name']:
                match['field'] = 'parent_name'
        
        # Extraer del contenido de texto COMPLETO
        if hasattr(file, 'document') and file.document and file.document.text_content:
            full_text = file.document.text_content
            all_matches['text_content'] = extract_matches(full_text, terms, exact_string)
            for match in all_matches['text_content']:
                match['field'] = 'text_content'
        
        # Extraer de la descripción COMPLETA
        if hasattr(file, 'document') and file.document and file.document.description:
            full_description = file.document.description
            all_matches['description'] = extract_matches(full_description, terms, exact_string)
            for match in all_matches['description']:
                match['field'] = 'description'
        
        return all_matches
    
    # Función para verificar si hay coincidencias en search_vector
    def has_search_vector_match(file, search_query):
        """
        Verifica si el archivo tiene coincidencias en search_vector
        """
        if not hasattr(file, 'document') or not file.document:
            return False
        return GoogleDriveFileDocument.objects.filter(
            file=file, 
            search_vector=search_query
        ).exists()
    
    # Función para verificar si hay coincidencias en description_vector
    def has_description_vector_match(file, search_query):
        """
        Verifica si el archivo tiene coincidencias en description_vector
        """
        if not hasattr(file, 'document') or not file.document:
            return False
        return GoogleDriveFileDocument.objects.filter(
            file=file, 
            description_vector=search_query
        ).exists()
    
    # Función para verificar si un archivo tiene ALGUNA coincidencia de texto
    def has_any_text_match(file, matched_texts):
        """
        Verifica si el archivo tiene al menos una coincidencia en algún campo
        """
        total_matches = sum(len(matches) for matches in matched_texts.values())
        return total_matches > 0
    
    # Construir resultados
    results = []
    for file in files:
        matched_texts = extract_all_matches(file, search_terms, search_string)
        
        # SOLO incluir archivos que tengan AL MENOS UNA coincidencia de texto
        if not has_any_text_match(file, matched_texts):
            continue  # Saltar este archivo
        
        matches_found = []
        
        # Obtener jerarquía completa
        hierarchy = get_full_hierarchy(file)
        full_path = get_full_path(file)
        
        # Determinar en qué campos se encontraron coincidencias
        # Usando word boundaries para verificar coincidencias de palabras completas
        
        # Verificar coincidencias en name
        if any(match['match_type'] == 'exact' for match in matched_texts.get('name', [])):
            matches_found.append('name_exact')
        elif any(has_word_match(file.name, term) for term in search_terms):
            matches_found.append('name')
        
        # Verificar coincidencias en parent_name
        if file.parent_drive_file_id:
            if any(match['match_type'] == 'exact' for match in matched_texts.get('parent_name', [])):
                matches_found.append('parent_name_exact')
            elif any(has_word_match(file.parent_drive_file_id.name, term) for term in search_terms):
                matches_found.append('parent_name')
        
        # Verificar coincidencias en text_content y description
        if hasattr(file, 'document') and file.document:
            # Coincidencias en text_content
            if any(match['match_type'] == 'exact' for match in matched_texts.get('text_content', [])):
                matches_found.append('text_content_exact')
            elif has_search_vector_match(file, search_query):
                matches_found.append('search_vector')
            
            # Coincidencias en description
            if any(match['match_type'] == 'exact' for match in matched_texts.get('description', [])):
                matches_found.append('description_exact')
            elif has_description_vector_match(file, search_query):
                matches_found.append('description_vector')
        
        # Contar coincidencias exactas vs términos
        exact_matches = sum(1 for field_matches in matched_texts.values() 
                          for m in field_matches if m.get('match_type') == 'exact')
        term_matches = sum(1 for field_matches in matched_texts.values() 
                         for m in field_matches if m.get('match_type') == 'term')
        
        # Construir el resultado
        result = {
            'id': str(file.id),
            'drive_file_id': file.drive_file_id,
            'name': file.name,
            'mime_type': file.mime_type,
            'hierarchy': hierarchy,
            'full_path': full_path,
            'parent_drive_file_id': file.parent_drive_file_id.drive_file_id if file.parent_drive_file_id else None,
            'parent_name': file.parent_drive_file_id.name if file.parent_drive_file_id else None,
            'drive_web_view_link': file.drive_web_view_link,
            'last_known_modified_time': file.last_known_modified_time.isoformat() if file.last_known_modified_time else None,
            'last_synced_at': file.last_synced_at.isoformat() if file.last_synced_at else None,
            'relevance_score': float(file.total_rank) if file.total_rank else 0,
            'relevance_details': {
                'exact_name_rank': float(file.exact_name_rank) if file.exact_name_rank else 0,
                'exact_parent_rank': float(file.exact_parent_rank) if file.exact_parent_rank else 0,
                'name_rank': float(file.name_rank) if file.name_rank else 0,
                'parent_rank': float(file.parent_rank) if file.parent_rank else 0,
                'search_vector_rank': float(file.search_vector_rank) if file.search_vector_rank else 0,
                'description_rank': float(file.description_rank) if file.description_rank else 0,
            },
            'matches_found_in': matches_found,
            'matched_texts': {
                'total_matches': sum(len(v) for v in matched_texts.values()),
                'exact_matches': exact_matches,
                'term_matches': term_matches,
                'by_field': {
                    field: {
                        'count': len(items),
                        'items': items[:10],
                        'exact_count': sum(1 for m in items if m.get('match_type') == 'exact'),
                        'term_count': sum(1 for m in items if m.get('match_type') == 'term')
                    }
                    for field, items in matched_texts.items() if items
                },
                'summary': {
                    field: {
                        'exact_terms': list(set(item['term'] for item in items if item.get('match_type') == 'exact')),
                        'terms': list(set(item['term'] for item in items if item.get('match_type') == 'term'))
                    }
                    for field, items in matched_texts.items() if items
                }
            },
            'area': file.area_id if file.area else None,
            'area_name': file.area.nombre if file.area else None,
        }
        
        # Información del documento
        if hasattr(file, 'document') and file.document:
            result['document'] = {
                'text_content_preview': file.document.text_content[:500] if file.document.text_content else None,
                'description': file.document.description,
            }
        
        results.append(result)
    
    return JsonResponse({
        'status': 'success',
        'search_string': search_string,
        'search_terms': search_terms,
        'total_results': len(results),
        'results': results
    }, json_dumps_params={'ensure_ascii': False})


from django.db.models import Q, F, Value, FloatField, Case, When
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models.functions import Coalesce
from django.http import JsonResponse
import unicodedata
import re

def search_google_drive_files_ranked(search_string):
    """
    Búsqueda con ranking de relevancia y extracción de textos coincidentes
    1) Primero busca exactamente el string ingresado y da el ranking mayor
    2) Luego usa search_string.split() para búsqueda más amplia
    Busca palabras completas usando word boundaries (\\b) para otros campos
    Incluye búsqueda flexible en el nombre del archivo (coincidencia parcial SIN boundaries)
    Ignora acentos en la búsqueda del nombre del archivo y del folder parent
    RANKING: 1) Nombre archivo, 2) Nombre folder parent, 3) Todo lo demás
    """
    # Dividir la búsqueda en términos y filtrar palabras de menos de 3 caracteres
    raw_terms = search_string.strip().split()
    # Filtrar palabras con menos de 3 caracteres (excluir "a", "de", "los", etc.)
    search_terms = [term for term in raw_terms if len(term) >= 3]
    
    if not search_terms:
        return JsonResponse({
            'status': 'error',
            'message': 'El término de búsqueda debe tener al menos 3 caracteres',
            'results': []
        })
    
    # Configurar la búsqueda en español
    search_query = SearchQuery(search_string, config='spanish')
    
    # Función para normalizar texto eliminando acentos
    def normalize_for_db(text):
        """
        Normaliza el texto eliminando acentos y convirtiendo a minúsculas
        """
        if not text:
            return ""
        # Convertir a minúsculas
        text = text.lower()
        # Eliminar acentos
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
        return text
    
    # Construir queries para búsqueda en texto
    # Búsqueda en nombre del archivo - BUSCAR AMBAS VERSIONES (con y sin acentos)
    name_queries = Q()
    for term in search_terms:
        # Buscar con el término original
        name_queries |= Q(name__icontains=term)
        # Buscar con el término sin acentos
        term_normalized = normalize_for_db(term)
        name_queries |= Q(name__icontains=term_normalized)
    
    # Búsqueda en nombre del padre (contiene el término) - BUSCAR AMBAS VERSIONES (con y sin acentos)
    parent_name_queries = Q()
    for term in search_terms:
        # Buscar con el término original
        parent_name_queries |= Q(parent_drive_file_id__name__icontains=term)
        # Buscar con el término sin acentos
        term_normalized = normalize_for_db(term)
        parent_name_queries |= Q(parent_drive_file_id__name__icontains=term_normalized)
    
    # Búsqueda principal con anotación de ranking
    files = GoogleDriveFile.objects.filter(
        Q(name_queries) |
        Q(parent_name_queries) |
        Q(document__search_vector=search_query) |
        Q(document__description_vector=search_query)
    ).distinct().select_related('parent_drive_file_id', 'document', 'area').annotate(
        # ================================================================
        # 1) RANKING PARA NOMBRE DE ARCHIVO (MÁXIMA PRIORIDAD)
        # ================================================================
        
        # Coincidencia EXACTA en nombre (máxima prioridad)
        exact_name_rank=Case(
            When(name__iexact=search_string, then=Value(100.0)),
            When(name__istartswith=search_string, then=Value(80.0)),
            When(name__icontains=search_string, then=Value(60.0)),
            default=Value(0.0),
            output_field=FloatField()
        ),
        # Coincidencia normalizada en nombre (sin acentos)
        name_normalized_rank=Case(
            When(name__icontains=normalize_for_db(search_string), then=Value(70.0)),
            default=Value(0.0),
            output_field=FloatField()
        ),
        # Coincidencia parcial de términos en nombre
        name_partial_rank=Case(
            When(name__icontains=normalize_for_db(search_terms[0]) if search_terms else "", then=Value(50.0)),
            default=Value(0.0),
            output_field=FloatField()
        ),
        # SearchRank para nombre
        name_rank=SearchRank(
            SearchVector('name', config='spanish'), 
            search_query
        ),
        
        # ================================================================
        # 2) RANKING PARA NOMBRE DE FOLDER PARENT (SEGUNDA PRIORIDAD)
        # ================================================================
        
        # Coincidencia EXACTA en parent_name
        exact_parent_rank=Case(
            When(parent_drive_file_id__name__iexact=search_string, then=Value(60.0)),
            When(parent_drive_file_id__name__istartswith=search_string, then=Value(40.0)),
            When(parent_drive_file_id__name__icontains=search_string, then=Value(30.0)),
            default=Value(0.0),
            output_field=FloatField()
        ),
        # Coincidencia normalizada en parent (sin acentos)
        parent_normalized_rank=Case(
            When(parent_drive_file_id__name__icontains=normalize_for_db(search_string), then=Value(35.0)),
            default=Value(0.0),
            output_field=FloatField()
        ),
        # Coincidencia parcial de términos en parent
        parent_partial_rank=Case(
            When(parent_drive_file_id__name__icontains=normalize_for_db(search_terms[0]) if search_terms else "", then=Value(20.0)),
            default=Value(0.0),
            output_field=FloatField()
        ),
        # SearchRank para parent_name
        parent_rank=SearchRank(
            SearchVector('parent_drive_file_id__name', config='spanish'), 
            search_query
        ),
        
        # ================================================================
        # 3) RANKING PARA CONTENIDO Y DESCRIPCIÓN (MENOR PRIORIDAD)
        # ================================================================
        
        # SearchRank para contenido de texto
        search_vector_rank=SearchRank(
            F('document__search_vector'), 
            search_query
        ),
        # SearchRank para descripción
        description_rank=SearchRank(
            F('document__description_vector'), 
            search_query
        ),
        
        # ================================================================
        # RANKING TOTAL PONDERADO
        # ================================================================
        total_rank=(
            # -------- 1) NOMBRE ARCHIVO (PESO MUY ALTO) --------
            Coalesce('exact_name_rank', Value(0.0, output_field=FloatField())) * 5.0 +
            Coalesce('name_normalized_rank', Value(0.0, output_field=FloatField())) * 4.0 +
            Coalesce('name_partial_rank', Value(0.0, output_field=FloatField())) * 3.0 +
            (Coalesce('name_rank', Value(0.0, output_field=FloatField())) * 3.0) +
            # -------- 2) NOMBRE FOLDER PARENT (PESO ALTO) --------
            Coalesce('exact_parent_rank', Value(0.0, output_field=FloatField())) * 2.0 +
            Coalesce('parent_normalized_rank', Value(0.0, output_field=FloatField())) * 1.5 +
            Coalesce('parent_partial_rank', Value(0.0, output_field=FloatField())) * 1.0 +
            (Coalesce('parent_rank', Value(0.0, output_field=FloatField())) * 1.0) +
            # -------- 3) CONTENIDO Y DESCRIPCIÓN (PESO BAJO) --------
            (Coalesce('search_vector_rank', Value(0.0, output_field=FloatField())) * 0.3) + 
            (Coalesce('description_rank', Value(0.0, output_field=FloatField())) * 0.2)
        )
    ).order_by('-total_rank')
    
    # Función para normalizar texto (elimina acentos, minúsculas, caracteres especiales)
    def normalize_text(text):
        """
        Normaliza el texto para búsqueda:
        - Elimina acentos
        - Convierte a minúsculas
        - Elimina caracteres especiales
        """
        if not text:
            return ""
        # Convertir a minúsculas
        text = text.lower()
        # Eliminar acentos
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
        # Eliminar caracteres especiales pero mantener palabras
        text = re.sub(r'[^\w\s]', ' ', text)
        # Reducir espacios múltiples
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    # Función para verificar si una palabra existe como palabra completa en un texto
    def has_word_match(text, term):
        """
        Verifica si un término existe como palabra completa en el texto
        Ignora acentos
        """
        if not text or not term:
            return False
        
        text_normalized = normalize_text(text)
        term_normalized = normalize_text(term)
        pattern = r'\b' + re.escape(term_normalized) + r'\b'
        return bool(re.search(pattern, text_normalized))
    
    # Función para verificar si un término existe en el texto (coincidencia parcial) - IGNORA ACENTOS
    # SIN boundaries - búsqueda flexible
    def has_partial_match(text, term):
        """
        Verifica si un término existe en el texto (coincidencia parcial)
        Ignora acentos
        SIN word boundaries - búsqueda flexible
        """
        if not text or not term:
            return False
        
        text_normalized = normalize_text(text)
        term_normalized = normalize_text(term)
        return term_normalized in text_normalized
    
    # Función para verificar coincidencia exacta en nombre (antes de normalizar)
    def has_exact_match_in_name(text, term):
        """
        Verifica si el término existe exactamente en el texto (sin normalizar)
        """
        if not text or not term:
            return False
        
        # Búsqueda exacta (case insensitive)
        return term.lower() in text.lower()
    
    # Función para obtener la jerarquía completa de carpetas padres
    def get_full_hierarchy(file_obj):
        """
        Obtiene la jerarquía completa de carpetas padres
        Retorna una lista de diccionarios con la información de cada nivel
        """
        hierarchy = []
        current = file_obj.parent_drive_file_id
        
        while current:
            hierarchy.insert(0, {
                'drive_file_id': current.drive_file_id,
                'name': current.name,
                'mime_type': current.mime_type,
            })
            current = current.parent_drive_file_id
        
        return hierarchy
    
    # Función para obtener la ruta completa como string
    def get_full_path(file_obj):
        """
        Obtiene la ruta completa como string separada por > 
        Ejemplo: "Raiz > Proyecto > Subcarpeta > Archivo"
        """
        hierarchy = get_full_hierarchy(file_obj)
        path_parts = [item['name'] for item in hierarchy]
        #if file_obj.name:
        #    path_parts.append(file_obj.name)
        return ' > '.join(path_parts)
    
    # Función auxiliar para extraer coincidencias de PALABRAS COMPLETAS
    def extract_matches(text, terms, exact_string=None):
        """
        Extrae fragmentos de texto que coinciden con los términos de búsqueda
        Usa word boundaries (\\b) para encontrar palabras completas
        """
        if not text:
            return []
        
        # Texto normalizado para buscar
        text_normalized = normalize_text(text)
        matches = []
        processed_positions = set()
        
        # Configurar tamaño del contexto (más grande para mostrar más texto)
        CONTEXT_SIZE = 80
        
        # 1) PRIMERO buscar coincidencias EXACTAS (prioridad máxima)
        if exact_string:
            exact_normalized = normalize_text(exact_string)
            # Buscar como palabra completa usando word boundaries
            pattern = r'\b' + re.escape(exact_normalized) + r'\b'
            for match in re.finditer(pattern, text_normalized):
                pos = match.start()
                if pos not in processed_positions:
                    context_start = max(0, pos - CONTEXT_SIZE)
                    context_end = min(len(text), pos + len(exact_string) + CONTEXT_SIZE)
                    fragment = text[context_start:context_end]
                    
                    # Resaltar el término en el contexto
                    highlighted_fragment = fragment.replace(
                        text[pos-context_start:pos-context_start+len(exact_string)],
                        f"**{exact_string}**"
                    ) if pos >= context_start else fragment
                    
                    matches.append({
                        'term': exact_string,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': highlighted_fragment.strip(),
                        'length': len(exact_string),
                        'match_type': 'exact',
                        'field': 'text_content'
                    })
                    processed_positions.add(pos)
        
        # 2) LUEGO buscar por términos separados (prioridad media)
        for term in terms:
            if term == exact_string:  # Saltar si ya se buscó como exacto
                continue
            
            term_normalized = normalize_text(term)
            # Buscar como palabra completa usando word boundaries
            pattern = r'\b' + re.escape(term_normalized) + r'\b'
            for match in re.finditer(pattern, text_normalized):
                pos = match.start()
                
                # Verificar que no sea parte de una coincidencia exacta ya encontrada
                is_duplicate = False
                for processed_pos in processed_positions:
                    if abs(pos - processed_pos) < len(exact_string) if exact_string else False:
                        is_duplicate = True
                        break
                
                if not is_duplicate and pos not in processed_positions:
                    context_start = max(0, pos - CONTEXT_SIZE)
                    context_end = min(len(text), pos + len(term) + CONTEXT_SIZE)
                    fragment = text[context_start:context_end]
                    
                    # Resaltar el término en el contexto
                    highlighted_fragment = fragment.replace(
                        text[pos-context_start:pos-context_start+len(term)],
                        f"**{term}**"
                    ) if pos >= context_start else fragment
                    
                    matches.append({
                        'term': term,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': highlighted_fragment.strip(),
                        'length': len(term),
                        'match_type': 'term',
                        'field': 'text_content'
                    })
                    processed_positions.add(pos)
        
        # Ordenar por posición y prioridad
        matches.sort(key=lambda x: (x['position'], 0 if x['match_type'] == 'exact' else 1))
        
        return matches
    
    # Función para extraer coincidencias con búsqueda flexible (parcial) - IGNORANDO ACENTOS
    # SIN boundaries - búsqueda flexible
    def extract_matches_flexible(text, terms, exact_string=None):
        """
        Extrae fragmentos de texto con búsqueda flexible (coincidencia parcial)
        Para usar en nombres de archivo
        Ignora acentos en la comparación
        SIN word boundaries - búsqueda flexible
        """
        if not text:
            return []
        
        # Texto normalizado para buscar (sin acentos)
        text_normalized = normalize_text(text)
        matches = []
        processed_positions = set()
        
        # Configurar tamaño del contexto
        CONTEXT_SIZE = 80
        
        # 1) PRIMERO buscar coincidencia EXACTA (antes de normalizar)
        if exact_string:
            # Buscar coincidencia exacta en el texto original (sin normalizar)
            if exact_string.lower() in text.lower():
                pos = text.lower().find(exact_string.lower())
                if pos not in processed_positions:
                    context_start = max(0, pos - CONTEXT_SIZE)
                    context_end = min(len(text), pos + len(exact_string) + CONTEXT_SIZE)
                    fragment = text[context_start:context_end]
                    
                    highlighted_fragment = fragment.replace(
                        text[pos-context_start:pos-context_start+len(exact_string)],
                        f"**{exact_string}**"
                    ) if pos >= context_start else fragment
                    
                    matches.append({
                        'term': exact_string,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': highlighted_fragment.strip(),
                        'length': len(exact_string),
                        'match_type': 'exact_original',
                        'field': 'name'
                    })
                    processed_positions.add(pos)
        
        # 2) LUEGO buscar coincidencias exactas normalizadas (ignorando acentos)
        if exact_string:
            exact_normalized = normalize_text(exact_string)
            if exact_normalized in text_normalized:
                pos = text_normalized.find(exact_normalized)
                # Verificar que no sea la misma posición que la coincidencia exacta original
                is_duplicate = False
                for processed_pos in processed_positions:
                    if abs(pos - processed_pos) < len(exact_string):
                        is_duplicate = True
                        break
                
                if not is_duplicate and pos not in processed_positions:
                    context_start = max(0, pos - CONTEXT_SIZE)
                    context_end = min(len(text), pos + len(exact_string) + CONTEXT_SIZE)
                    fragment = text[context_start:context_end]
                    
                    highlighted_fragment = fragment.replace(
                        text[pos-context_start:pos-context_start+len(exact_string)],
                        f"**{exact_string}**"
                    ) if pos >= context_start else fragment
                    
                    matches.append({
                        'term': exact_string,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': highlighted_fragment.strip(),
                        'length': len(exact_string),
                        'match_type': 'exact_normalized',
                        'field': 'name'
                    })
                    processed_positions.add(pos)
        
        # 3) FINALMENTE buscar términos individuales (sin boundaries) - name_partial
        for term in terms:
            if term == exact_string:
                continue
            
            term_normalized = normalize_text(term)
            if term_normalized in text_normalized:
                pos = text_normalized.find(term_normalized)
                
                is_duplicate = False
                for processed_pos in processed_positions:
                    if abs(pos - processed_pos) < len(term):
                        is_duplicate = True
                        break
                
                if not is_duplicate and pos not in processed_positions:
                    context_start = max(0, pos - CONTEXT_SIZE)
                    context_end = min(len(text), pos + len(term) + CONTEXT_SIZE)
                    fragment = text[context_start:context_end]
                    
                    highlighted_fragment = fragment.replace(
                        text[pos-context_start:pos-context_start+len(term)],
                        f"**{term}**"
                    ) if pos >= context_start else fragment
                    
                    matches.append({
                        'term': term,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': highlighted_fragment.strip(),
                        'length': len(term),
                        'match_type': 'partial',
                        'field': 'name'
                    })
                    processed_positions.add(pos)
        
        matches.sort(key=lambda x: (x['position'], 0 if x['match_type'] in ['exact_original', 'exact_normalized'] else 1))
        return matches
    
    # Función para extraer coincidencias de parent_name (folders) - CON boundaries Y IGNORANDO ACENTOS
    def extract_parent_matches(text, terms, exact_string=None):
        """
        Extrae fragmentos de texto de parent_name (folders)
        Usa word boundaries para palabras completas
        Ignora acentos en la comparación
        """
        if not text:
            return []
        
        # Normalizar el texto para buscar (sin acentos)
        text_normalized = normalize_text(text)
        matches = []
        processed_positions = set()
        CONTEXT_SIZE = 80
        
        # 1) Buscar coincidencias exactas (con word boundaries)
        if exact_string:
            exact_normalized = normalize_text(exact_string)
            pattern = r'\b' + re.escape(exact_normalized) + r'\b'
            for match in re.finditer(pattern, text_normalized):
                pos = match.start()
                if pos not in processed_positions:
                    context_start = max(0, pos - CONTEXT_SIZE)
                    context_end = min(len(text), pos + len(exact_string) + CONTEXT_SIZE)
                    fragment = text[context_start:context_end]
                    highlighted_fragment = fragment.replace(
                        text[pos-context_start:pos-context_start+len(exact_string)],
                        f"**{exact_string}**"
                    ) if pos >= context_start else fragment
                    
                    matches.append({
                        'term': exact_string,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': highlighted_fragment.strip(),
                        'length': len(exact_string),
                        'match_type': 'exact',
                        'field': 'parent_name'
                    })
                    processed_positions.add(pos)
        
        # 2) Buscar términos individuales (con word boundaries y sin acentos)
        for term in terms:
            if term == exact_string:
                continue
            term_normalized = normalize_text(term)
            pattern = r'\b' + re.escape(term_normalized) + r'\b'
            for match in re.finditer(pattern, text_normalized):
                pos = match.start()
                is_duplicate = False
                for processed_pos in processed_positions:
                    if abs(pos - processed_pos) < len(exact_string) if exact_string else False:
                        is_duplicate = True
                        break
                if not is_duplicate and pos not in processed_positions:
                    context_start = max(0, pos - CONTEXT_SIZE)
                    context_end = min(len(text), pos + len(term) + CONTEXT_SIZE)
                    fragment = text[context_start:context_end]
                    highlighted_fragment = fragment.replace(
                        text[pos-context_start:pos-context_start+len(term)],
                        f"**{term}**"
                    ) if pos >= context_start else fragment
                    matches.append({
                        'term': term,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': highlighted_fragment.strip(),
                        'length': len(term),
                        'match_type': 'term',
                        'field': 'parent_name'
                    })
                    processed_positions.add(pos)
        
        # 3) Si no hay coincidencias con word boundaries, buscar coincidencia parcial (sin boundaries)
        # Esto permite encontrar "politica" en "política" aunque no sea palabra completa
        if not matches:
            for term in terms:
                if term == exact_string:
                    continue
                term_normalized = normalize_text(term)
                if term_normalized in text_normalized:
                    pos = text_normalized.find(term_normalized)
                    context_start = max(0, pos - CONTEXT_SIZE)
                    context_end = min(len(text), pos + len(term) + CONTEXT_SIZE)
                    fragment = text[context_start:context_end]
                    highlighted_fragment = fragment.replace(
                        text[pos-context_start:pos-context_start+len(term)],
                        f"**{term}**"
                    ) if pos >= context_start else fragment
                    matches.append({
                        'term': term,
                        'position': pos,
                        'context': fragment.strip(),
                        'highlighted': highlighted_fragment.strip(),
                        'length': len(term),
                        'match_type': 'partial',
                        'field': 'parent_name'
                    })
                    processed_positions.add(pos)
        
        matches.sort(key=lambda x: (x['position'], 0 if x['match_type'] == 'exact' else 1))
        return matches
    
    def extract_all_matches(file, terms, exact_string):
        """
        Extrae coincidencias de todos los campos del archivo
        Incluye búsqueda flexible en el nombre del archivo
        """
        all_matches = {
            'name': [],
            'parent_name': [],
            'text_content': [],
            'description': []
        }
        
        # Extraer del nombre del archivo - Usar búsqueda FLEXIBLE (parcial) SIN boundaries
        if file.name:
            all_matches['name'] = extract_matches_flexible(file.name, terms, exact_string)
            for match in all_matches['name']:
                match['field'] = 'name'
        
        # Extraer del nombre del padre - Usar búsqueda CON boundaries Y sin acentos
        if file.parent_drive_file_id and file.parent_drive_file_id.name:
            all_matches['parent_name'] = extract_parent_matches(file.parent_drive_file_id.name, terms, exact_string)
            for match in all_matches['parent_name']:
                match['field'] = 'parent_name'
        
        # Extraer del contenido de texto COMPLETO - Usar búsqueda de palabras completas
        if hasattr(file, 'document') and file.document and file.document.text_content:
            full_text = file.document.text_content
            all_matches['text_content'] = extract_matches(full_text, terms, exact_string)
            for match in all_matches['text_content']:
                match['field'] = 'text_content'
        
        # Extraer de la descripción COMPLETA - Usar búsqueda de palabras completas
        if hasattr(file, 'document') and file.document and file.document.description:
            full_description = file.document.description
            all_matches['description'] = extract_matches(full_description, terms, exact_string)
            for match in all_matches['description']:
                match['field'] = 'description'
        
        return all_matches
    
    # Función para verificar si hay coincidencias en search_vector
    def has_search_vector_match(file, search_query):
        """
        Verifica si el archivo tiene coincidencias en search_vector
        """
        if not hasattr(file, 'document') or not file.document:
            return False
        return GoogleDriveFileDocument.objects.filter(
            file=file, 
            search_vector=search_query
        ).exists()
    
    # Función para verificar si hay coincidencias en description_vector
    def has_description_vector_match(file, search_query):
        """
        Verifica si el archivo tiene coincidencias en description_vector
        """
        if not hasattr(file, 'document') or not file.document:
            return False
        return GoogleDriveFileDocument.objects.filter(
            file=file, 
            description_vector=search_query
        ).exists()
    
    # Función para verificar si un archivo tiene ALGUNA coincidencia de texto
    def has_any_text_match(file, matched_texts):
        """
        Verifica si el archivo tiene al menos una coincidencia en algún campo
        """
        total_matches = sum(len(matches) for matches in matched_texts.values())
        return total_matches > 0
    
    # Construir resultados con filtro en Python para el nombre
    results = []
    for file in files:
        # 1) PRIMERO verificar coincidencia exacta en nombre (antes de normalizar)
        exact_match_in_name = False
        file_name = file.name if file.name else ""
        
        # Buscar coincidencia exacta del search_string completo
        if search_string.lower() in file_name.lower():
            exact_match_in_name = True
        
        # 2) Verificar coincidencia normalizada (ignorando acentos)
        exact_normalized_match = False
        search_string_normalized = normalize_text(search_string)
        file_name_normalized = normalize_text(file.name) if file.name else ""
        
        if search_string_normalized in file_name_normalized:
            exact_normalized_match = True
        
        # 3) Si no hay coincidencia exacta, buscar coincidencia parcial (ignorando acentos)
        name_matches = False
        for term in search_terms:
            term_normalized = normalize_text(term)
            if term_normalized in file_name_normalized:
                name_matches = True
                break
        
        # 4) Verificar coincidencias en parent_name (folders) - IGNORANDO ACENTOS
        parent_matches = False
        if file.parent_drive_file_id and file.parent_drive_file_id.name:
            parent_name = file.parent_drive_file_id.name
            parent_name_normalized = normalize_text(parent_name)
            for term in search_terms:
                term_normalized = normalize_text(term)
                if term_normalized in parent_name_normalized:
                    parent_matches = True
                    break
        
        # Si el archivo NO coincide en nombre, ni en parent, ni en otros campos, saltar
        if not exact_match_in_name and not exact_normalized_match and not name_matches and not parent_matches:
            # Verificar si coincide en otros campos
            has_other_match = False
            
            # Verificar document content
            if hasattr(file, 'document') and file.document:
                if has_search_vector_match(file, search_query) or has_description_vector_match(file, search_query):
                    has_other_match = True
            
            # Si no tiene coincidencias en otros campos, saltar
            if not has_other_match:
                continue
        
        # Extraer coincidencias de todos los campos
        matched_texts = extract_all_matches(file, search_terms, search_string)
        
        matches_found = []
        
        # Obtener jerarquía completa
        hierarchy = get_full_hierarchy(file)
        full_path = get_full_path(file)
        
        # Determinar en qué campos se encontraron coincidencias
        # -------- 1) NOMBRE ARCHIVO (MÁXIMA PRIORIDAD) --------
        if any(match['match_type'] == 'exact_original' for match in matched_texts.get('name', [])):
            matches_found.append('name_exact_original')
        elif any(match['match_type'] == 'exact_normalized' for match in matched_texts.get('name', [])):
            matches_found.append('name_exact_normalized')
        elif any(match['match_type'] == 'partial' for match in matched_texts.get('name', [])):
            matches_found.append('name_partial')
        elif exact_match_in_name:
            matches_found.append('name_exact')
        elif exact_normalized_match:
            matches_found.append('name_exact_normalized')
        elif name_matches:
            matches_found.append('name')
        
        # -------- 2) NOMBRE FOLDER PARENT (SEGUNDA PRIORIDAD) --------
        if file.parent_drive_file_id:
            # Verificar coincidencias exactas en parent_name
            if any(match['match_type'] == 'exact' for match in matched_texts.get('parent_name', [])):
                matches_found.append('parent_name_exact')
            elif any(match['match_type'] == 'term' for match in matched_texts.get('parent_name', [])):
                matches_found.append('parent_name')
            elif parent_matches:
                matches_found.append('parent_name_partial')
        
        # -------- 3) CONTENIDO Y DESCRIPCIÓN (MENOR PRIORIDAD) --------
        if hasattr(file, 'document') and file.document:
            if any(match['match_type'] == 'exact' for match in matched_texts.get('text_content', [])):
                matches_found.append('text_content_exact')
            elif has_search_vector_match(file, search_query):
                matches_found.append('search_vector')
            
            if any(match['match_type'] == 'exact' for match in matched_texts.get('description', [])):
                matches_found.append('description_exact')
            elif has_description_vector_match(file, search_query):
                matches_found.append('description_vector')
        
        # Si no hay matches_found, pero tiene coincidencias en nombre o parent, agregarlo
        if not matches_found and (exact_match_in_name or exact_normalized_match or name_matches or parent_matches):
            if exact_match_in_name:
                matches_found.append('name_exact')
            elif exact_normalized_match:
                matches_found.append('name_exact_normalized')
            elif name_matches:
                matches_found.append('name')
            elif parent_matches:
                matches_found.append('parent_name_partial')
        
        # Contar coincidencias exactas vs términos
        exact_matches = sum(1 for field_matches in matched_texts.values() 
                          for m in field_matches if m.get('match_type') in ['exact', 'exact_original', 'exact_normalized'])
        term_matches = sum(1 for field_matches in matched_texts.values() 
                         for m in field_matches if m.get('match_type') in ['term', 'partial'])
        
        # Si no hay matched_texts pero tiene name_matches o parent_matches, agregar al menos una coincidencia
        if exact_matches == 0 and term_matches == 0 and (exact_match_in_name or exact_normalized_match or name_matches or parent_matches):
            term_matches = 1
        
        # Construir el resultado
        result = {
            'id': str(file.id),
            'drive_file_id': file.drive_file_id,
            'name': file.name,
            'mime_type': file.mime_type,
            'hierarchy': hierarchy,
            'full_path': full_path,
            'parent_drive_file_id': file.parent_drive_file_id.drive_file_id if file.parent_drive_file_id else None,
            'parent_name': file.parent_drive_file_id.name if file.parent_drive_file_id else None,
            'drive_web_view_link': file.drive_web_view_link,
            'last_known_modified_time': file.last_known_modified_time.isoformat() if file.last_known_modified_time else None,
            'last_synced_at': file.last_synced_at.isoformat() if file.last_synced_at else None,
            'relevance_score': float(file.total_rank) if file.total_rank else 0,
            'relevance_details': {
                # Nombre archivo
                'exact_name_rank': float(file.exact_name_rank) if file.exact_name_rank else 0,
                'name_normalized_rank': float(file.name_normalized_rank) if hasattr(file, 'name_normalized_rank') else 0,
                'name_partial_rank': float(file.name_partial_rank) if hasattr(file, 'name_partial_rank') else 0,
                'name_rank': float(file.name_rank) if file.name_rank else 0,
                # Nombre folder parent
                'exact_parent_rank': float(file.exact_parent_rank) if file.exact_parent_rank else 0,
                'parent_normalized_rank': float(file.parent_normalized_rank) if hasattr(file, 'parent_normalized_rank') else 0,
                'parent_partial_rank': float(file.parent_partial_rank) if hasattr(file, 'parent_partial_rank') else 0,
                'parent_rank': float(file.parent_rank) if file.parent_rank else 0,
                # Contenido y descripción
                'search_vector_rank': float(file.search_vector_rank) if file.search_vector_rank else 0,
                'description_rank': float(file.description_rank) if file.description_rank else 0,
            },
            'matches_found_in': matches_found,
            'matched_texts': {
                'total_matches': sum(len(v) for v in matched_texts.values()) + (1 if (exact_match_in_name or exact_normalized_match or name_matches or parent_matches) and not any(matched_texts.values()) else 0),
                'exact_matches': exact_matches,
                'term_matches': term_matches,
                'by_field': {
                    field: {
                        'count': len(items),
                        'items': items[:10],
                        'exact_count': sum(1 for m in items if m.get('match_type') in ['exact', 'exact_original', 'exact_normalized']),
                        'term_count': sum(1 for m in items if m.get('match_type') in ['term', 'partial'])
                    }
                    for field, items in matched_texts.items() if items
                },
                'summary': {
                    field: {
                        'exact_terms': list(set(item['term'] for item in items if item.get('match_type') in ['exact', 'exact_original', 'exact_normalized'])),
                        'terms': list(set(item['term'] for item in items if item.get('match_type') in ['term', 'partial']))
                    }
                    for field, items in matched_texts.items() if items
                }
            },
            'area': file.area_id if file.area else None,
            'area_name': file.area.nombre if file.area else None,
        }
        
        # Información del documento
        if hasattr(file, 'document') and file.document:
            result['document'] = {
                'text_content_preview': file.document.text_content[:500] if file.document.text_content else None,
                'description': file.document.description,
            }
        
        results.append(result)
    
    return JsonResponse({
        'status': 'success',
        'search_string': search_string,
        'search_terms': search_terms,
        'total_results': len(results),
        'results': results
    }, json_dumps_params={'ensure_ascii': False})
 

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import F, Q, Value, FloatField, Case, When
from django.db.models.functions import Coalesce
from django.http import JsonResponse
import re
from django.contrib.postgres.lookups import Unaccent
from django.db.models import CharField, TextField


class GoogleDriveSearchService:
    """
    Clase de servicio encargada de realizar búsquedas avanzadas con Ranking,
    Vectores de texto completo y soporte estricto de desacentuación (unaccent).
    """

    @classmethod
    def execute(cls, search_string: str):
       
        # Registramos 'unaccent' para que esté disponible en cualquier campo de texto
        CharField.register_lookup(Unaccent)
        TextField.register_lookup(Unaccent)
       
        """
        Ejecuta la búsqueda replicando la lógica SQL de desacentuación y ranking.
        Retorna un QuerySet de GoogleDriveFile anotado con 'rank'.
        """
        search_string = search_string.strip() if search_string else ""
        
        if not search_string:
            return GoogleDriveFile.objects.none()

        # Dividir la búsqueda en términos y filtrar palabras de menos de 3 caracteres
        raw_terms = search_string.strip().split()
        # Filtrar palabras con menos de 3 caracteres (excluir "a", "de", "los", etc.)
        search_terms = [term for term in raw_terms if len(term) >= 3]
        
        if not search_terms:
            return GoogleDriveFile.objects.none()

        # 1. Limpiar el string y generar los términos para el to_tsquery (operador OR '|')
        # Usamos search_terms filtrados en lugar de todas las palabras
        search_query = SearchQuery(search_terms[0], config='spanish')
        for term in search_terms[1:]:
            search_query |= SearchQuery(term, config='spanish')

        # 2. Definir los vectores de búsqueda con sus respectivos pesos (setweight)
        vector_nombre_archivo = SearchVector('name', config='spanish', weight='A')
        vector_nombre_padre = SearchVector('parent_drive_file_id__name', config='spanish', weight='B')
        vector_documento = SearchVector('document__search_vector', config='spanish')
        vector_descripcion = SearchVector('document__description_vector', config='spanish')

        # Concatenación de vectores (equivalente al operador || en SQL)
        vector_total = vector_nombre_archivo + vector_nombre_padre + vector_documento + vector_descripcion
        logger.info(str(search_query)+"<----")
        # 3. Construir la consulta con el ORM de Django
        queryset = (
            GoogleDriveFile.objects
            .annotate(
                # Ranking por título del archivo (name) - MAYOR PESO
                name_rank=SearchRank(vector_nombre_archivo, search_query),
                # Ranking por nombre del padre
                parent_rank=SearchRank(vector_nombre_padre, search_query),
                # Ranking por contenido del documento
                document_rank=SearchRank(vector_documento, search_query),
                # Ranking por descripción
                description_rank=SearchRank(vector_descripcion, search_query),
                # Ranking total ponderado (nombre archivo tiene MAYOR peso)
                rank=(
                    # PESO MUY ALTO para nombre del archivo (título)
                    Coalesce('name_rank', Value(0.0, output_field=FloatField())) * 5.0 +
                    # Peso alto para nombre del padre
                    Coalesce('parent_rank', Value(0.0, output_field=FloatField())) * 2.0 +
                    # Peso medio para contenido del documento
                    Coalesce('document_rank', Value(0.0, output_field=FloatField())) * 0.5 +
                    # Peso bajo para descripción
                    Coalesce('description_rank', Value(0.0, output_field=FloatField())) * 0.3
                )
            )
            .filter(
                # Búsqueda SIN boundaries en nombre del archivo (título) - usamos icontains
                Q(name__unaccent__icontains=search_string) |
                # Búsqueda CON boundaries en nombre del archivo (título) - usamos word boundaries
                # Busca coincidencias exactas de palabras completas
                Q(name__unaccent__iexact=search_string) |
                Q(name__unaccent__istartswith=search_string) |
                # Búsqueda SIN boundaries en nombre del padre
                Q(parent_drive_file_id__name__unaccent__icontains=search_string) |
                # Búsqueda por vector de documento y descripción
                Q(document__search_vector=search_query) |
                Q(document__description_vector=search_query)
            )
            .filter(rank__gt=0.01)  # Filtro de control de ruido
            .select_related('parent_drive_file_id', 'document')  # Optimización de Joins
            .order_by('-rank')
        )

        return queryset

    @classmethod
    def _get_full_hierarchy(cls, file_obj):
        """
        Obtiene la jerarquía completa de carpetas padres.
        Retorna una lista de nombres desde la raíz hasta el padre más cercano.
        """
        hierarchy = []
        current = file_obj.parent_drive_file_id
        
        while current:
            hierarchy.insert(0, current.name)
            current = current.parent_drive_file_id
        
        return hierarchy

    @classmethod
    def _get_full_path(cls, file_obj):
        """
        Obtiene la ruta completa como string separada por ' > '.
        Ejemplo: "Raiz > Proyecto > Subcarpeta > Archivo"
        """
        hierarchy = cls._get_full_hierarchy(file_obj)
        path_parts = hierarchy.copy()
        #if file_obj.name:
        #    path_parts.append(file_obj.name)
        return ' > '.join(path_parts)

    @classmethod
    def execute_as_json_ready(cls, search_string: str) -> dict:
        """
        Ejecuta la búsqueda y formatea los resultados listos para una respuesta JSON.
        Incluye la jerarquía completa de carpetas y el relevance_score.
        """
        resultados = cls.execute(search_string)
        
        datos_resultado = []
        for archivo in resultados:
            # Obtener jerarquía completa
            hierarchy = cls._get_full_hierarchy(archivo)
            full_path = cls._get_full_path(archivo)
            
            # Calcular relevance_score como porcentaje (0-100) basado en el rank máximo posible
            max_possible_rank = 7.8
            relevance_score = min((float(archivo.rank) / max_possible_rank) * 100, 100)
            
            datos_resultado.append({
                "id": str(archivo.id),
                "drive_file_id": archivo.drive_file_id,
                "name": archivo.name,
                "mime_type": archivo.mime_type,
                "parent_name": archivo.parent_drive_file_id.name if archivo.parent_drive_file_id else None,
                "link": archivo.drive_web_view_link,
                "ranking": float(archivo.rank),
                "relevance_score": round(relevance_score, 2),
                "hierarchy": hierarchy,
                "full_path": full_path,
                "rank_details": {
                    "name_rank": float(archivo.name_rank) if hasattr(archivo, 'name_rank') else 0,
                    "parent_rank": float(archivo.parent_rank) if hasattr(archivo, 'parent_rank') else 0,
                    "document_rank": float(archivo.document_rank) if hasattr(archivo, 'document_rank') else 0,
                    "description_rank": float(archivo.description_rank) if hasattr(archivo, 'description_rank') else 0,
                }
            })
        return JsonResponse({
                'status': 'success',
                'search_string': search_string,
                'search_terms': search_terms if 'search_terms' in locals() else [],
                'total': len(datos_resultado),
                'results': datos_resultado
            }, json_dumps_params={'ensure_ascii': False})