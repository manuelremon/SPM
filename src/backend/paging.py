def parse_paging_args(args, allowed_sort):
    try:
        page = max(1, int(args.get('page', 1)))
    except: page = 1
    try:
        per_page = int(args.get('per_page', 20))
    except: per_page = 20
    per_page = min(max(per_page, 1), 100)
    q = (args.get('q') or '').strip()
    sort = args.get('sort') or 'created_at'
    if sort not in allowed_sort: sort = 'created_at'
    order = args.get('order','desc').lower()
    order = 'asc' if order == 'asc' else 'desc'
    return page, per_page, q, sort, order