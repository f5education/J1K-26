def instructions():
    try:
        ######## INSERT YOUR INSTRUCTIONS BELOW THIS LINE ########
        status, ip_addr = ec2_start_instance("lee-new-arcadia")

        namespace = xc_create_namespace()       
        xc_create_healthcheck(namespace, "lee-hc")
        xc_create_originpool(namespace, "lee-op", "lee-hc", ip_addr, 80)
        xc_create_loadbalancer(namespace, "lee-lb-na", "lee-lb-na.dev.learnf5.cloud", "lee-op")
        xc_create_loadbalancer(namespace, "lee-lb-eu", "lee-lb-eu.dev.learnf5.cloud", "lee-op")

        xc_create_healthcheck("default", "arcadia-na-hc")
        xc_create_originpool("default", "arcadia-na-op", "arcadia-na-hc", ip_addr, 80)    
        xc_create_loadbalancer("default", "aracdia-na-lb", "arcadia-na.dev.learnf5.cloud", "arcadia-na-op")     # intentionally mispelled
        xc_create_loadbalancer("default", "aracdia-eu-lb", "arcadia-eu.dev.learnf5.cloud", "arcadia-na-op")     # intentionally mispelled
        ######## INSERT YOUR INSTRUCTIONS ABOVE THIS LINE ########

    except Exception as e:
        return {
            'statusCode': 500,
            'errorMsg': json.dumps(str(e))
        }

    return {
        'statusCode': 200,
        'body': json.dumps({
            ######## ADJUST PARAMETERS THAT YOU WANT RETURNED TO SKILLABLE BELOW THIS LINE ########
            'status': status,
            'ip_addr': ip_addr,
            'namespace': namespace
            ######## ADJUST PARAMETERS THAT YOU WANT RETURNED TO SKILLABLE ABOVE THIS LINE ########
        })
    }
