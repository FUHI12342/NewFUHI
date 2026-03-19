"""統一APIレスポンスヘルパー"""
from django.http import JsonResponse


def success_response(data=None, status=200, meta=None):
    """成功レスポンス: {"success": true, "data": ..., "meta": ...}"""
    body = {'success': True, 'data': data}
    if meta:
        body['meta'] = meta
    return JsonResponse(body, status=status)


def error_response(error, status=400, code=None):
    """エラーレスポンス: {"success": false, "error": ..., "code": ...}"""
    body = {'success': False, 'error': error}
    if code:
        body['code'] = code
    return JsonResponse(body, status=status)


def list_response(results, total, page=None, limit=None):
    """一覧レスポンス: {"success": true, "data": {"results": ..., "total": ...}}"""
    data = {'results': results, 'total': total}
    if page is not None:
        data['page'] = page
    if limit is not None:
        data['limit'] = limit
    return JsonResponse({'success': True, 'data': data})
