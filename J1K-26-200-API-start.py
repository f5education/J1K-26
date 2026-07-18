def instructions():
    try:
        namespace = xc_create_user_and_namespace()
        _, ip_addr = ec2_create_instance('crAPI-template', namespace + "-app")
        xc_create_healthcheck(namespace, namespace + "-hc")
        xc_create_originpool(namespace, namespace + "-op", namespace + "-hc", [ip_addr], 30080)
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
            'namespace': namespace,
            'ip_addr': ip_addr
        })
    }
