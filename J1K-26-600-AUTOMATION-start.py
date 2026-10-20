def instructions():
    try:
        namespace  = xc_create_user_and_namespace()
        # tenant_api = xc_create_api_token()
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'errorMsg': f'ERROR: {str(e)}'
            })
        }

    return {
        'statusCode': 200,
        'body': json.dumps({
            'namespace': namespace # ,
            # 'tenant_api': tenant_api
        })
    }
