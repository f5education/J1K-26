def instructions():
    try:
        ######## INSERT YOUR INSTRUCTIONS BELOW THIS LINE ########
        #status, ip_addr = ec2_start_instance("jp-arc1-na")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Submit tasks
            futures_jp_ap1_eu = executor.submit(ec2_start_instance, "jp-ap1-eu")
            futures_jp_ap1_na = executor.submit(ec2_start_instance, "jp-ap1-na")
            # Retrieve results
            _, ip_addr_jp_ap1_eu = futures_jp_ap1_eu.result()
            _, ip_addr_jp_ap1_na = futures_jp_ap1_na.result()
        
        namespace = xc_create_user_and_namespace()
        
        # xc_create_healthcheck(namespace, namespace + "-hc")
        # xc_create_originpool(namespace, namespace + "-op", namespace + "-hc", ip_addr, 80)
        # xc_create_loadbalancer(namespace, namespace + "-lb-na", namespace + "-lb-na.dev.learnf5.cloud", namespace + "-op")
        # xc_create_loadbalancer(namespace, namespace + "-lb-eu", namespace + "-lb-eu.dev.learnf5.cloud", namespace + "-op")

        # xc_create_healthcheck("default", "arcadia-na-hc")
        # xc_create_originpool("default", "arcadia-na-op", "arcadia-na-hc", ip_addr, 80)    
        # xc_create_loadbalancer("default", "arcadia-na-lb", "arcadia-na.dev.learnf5.cloud", "arcadia-na-op")
        # xc_create_loadbalancer("default", "arcadia-eu-lb", "arcadia-eu.dev.learnf5.cloud", "arcadia-na-op")
        ######## INSERT YOUR INSTRUCTIONS ABOVE THIS LINE ########

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
            ######## ADJUST PARAMETERS THAT YOU WANT RETURNED TO SKILLABLE BELOW THIS LINE ########
            #'status': status,
            #'ip_addr': ip_addr,
            'ip_addr_jp_ap1_eu': ip_addr_jp_ap1_eu,
            'ip_addr_jp_ap1_na': ip_addr_jp_ap1_na,
            'namespace': namespace
            ######## ADJUST PARAMETERS THAT YOU WANT RETURNED TO SKILLABLE ABOVE THIS LINE ########
        })
    }
