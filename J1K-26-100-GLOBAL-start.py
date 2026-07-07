def instructions():
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            # Submit tasks
            futures_jp_arc1_eu = executor.submit(ec2_start_instance, "jp-arc1-eu")
            futures_jp_arc1_na = executor.submit(ec2_start_instance, "jp-arc1-na")
            futures_jp_arc1_jp = executor.submit(ec2_start_instance, "jp-arc1-jp")
            futures_jp_ap1_eu = executor.submit(ec2_start_instance, "jp-ap1-eu")
            futures_jp_ap1_na = executor.submit(ec2_start_instance, "jp-ap1-na")
            futures_jp_ap1_jp = executor.submit(ec2_start_instance, "jp-ap1-jp")
            # Retrieve results
            _, ip_addr_jp_arc1_eu = futures_jp_arc1_eu.result()
            _, ip_addr_jp_arc1_na = futures_jp_arc1_na.result()
            _, ip_addr_jp_arc1_jp = futures_jp_arc1_jp.result()
            _, ip_addr_jp_ap1_eu = futures_jp_ap1_eu.result()
            _, ip_addr_jp_ap1_na = futures_jp_ap1_na.result()
            _, ip_addr_jp_ap1_jp = futures_jp_ap1_jp.result()
        
        namespace = xc_create_user_and_namespace()
        xc_create_healthcheck(namespace, namespace + "-tls-hc")
        xc_create_healthcheck(namespace, namespace + "-arc-hc")
        xc_create_originpool(namespace, namespace + "-tls-op", namespace + "-tls-hc", [ip_addr_jp_ap1_eu, ip_addr_jp_ap1_na, ip_addr_jp_ap1_jp], 80)
        xc_create_originpool(namespace, namespace + "-arc-na-op", namespace + "-arc-hc", [ip_addr_jp_arc1_na], 80)
        xc_create_originpool(namespace, namespace + "-arc-eu-op", namespace + "-arc-hc", [ip_addr_jp_arc1_eu], 80)
        tls_conf = {
            "custom_security": {
                "cipher_suites": [
                    "TLS_RSA_WITH_AES_128_CBC_SHA"
                ],
                "max_version": "TLSv1_0",
                "min_version": "TLSv1_0"
            }
        }
        xc_create_loadbalancer(namespace, namespace + "-tls-lb", namespace + ".tls.f5training7.cloud", namespace + "-tls-op", tls_config = tls_conf)
        xc_create_loadbalancer(namespace, namespace + "-arc-na-lb", namespace + "-arcadia-na.f5training7.cloud", namespace + "-arc-na-op")
        xc_create_loadbalancer(namespace, namespace + "-arc-eu-lb", namespace + "-arcadia-eu.f5training7.cloud", namespace + "-arc-eu-op")
        
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
            'ip_addr_jp_arc1_eu': ip_addr_jp_arc1_eu,
            'ip_addr_jp_arc1_na': ip_addr_jp_arc1_na,
            'ip_addr_jp_arc1_jp': ip_addr_jp_arc1_jp,
            'ip_addr_jp_ap1_eu': ip_addr_jp_ap1_eu,
            'ip_addr_jp_ap1_na': ip_addr_jp_ap1_na,
            'ip_addr_jp_ap1_jp': ip_addr_jp_ap1_jp,
            'namespace': namespace
        })
    }
