def instructions():
    try:
        namespace = xc_create_user_and_namespace()
        xc_create_healthcheck(namespace, namespace + "-hc")
        xc_create_originpool(namespace, namespace + "-op", namespace + "-hc", [54.211.5.17], 80)
        xc_create_loadbalancer(namespace, namespace + "-lb", namespace + "-api.f5training7.cloud", namespace + "-op")

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
            'namespace': namespace
        })
    }
