def instructions():
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            # Submit tasks
            futures_jp_arc1_eu = executor.submit(ec2_start_instance, "jp-arc1-eu")
            futures_jp_arc1_na = executor.submit(ec2_start_instance, "jp-arc1-na")
            futures_jp_arc1_jp = executor.submit(ec2_start_instance, "jp-arc1-jp")
            futures_jp_arc1_eu = executor.submit(ec2_start_instance, "jp-ap1-eu")
            futures_jp_arc1_na = executor.submit(ec2_start_instance, "jp-ap1-na")
            futures_jp_arc1_jp = executor.submit(ec2_start_instance, "jp-ap1-jp")
            # Retrieve results
            _, ip_addr_jp_arc1_eu = futures_jp_arc1_eu.result()
            _, ip_addr_jp_arc1_na = futures_jp_arc1_na.result()
            _, ip_addr_jp_arc1_jp = futures_jp_arc1_jp.result()
            _, ip_addr_jp_arc1_eu = futures_jp_ap1_eu.result()
            _, ip_addr_jp_arc1_na = futures_jp_ap1_na.result()
            _, ip_addr_jp_arc1_jp = futures_jp_ap1_jp.result()
        
        namespace = xc_create_user_and_namespace()
        xc_create_healthcheck(namespace, namespace + "-hc")
        xc_create_originpool(namespace, namespace + "-op", namespace + "-hc", [ip_addr_jp_ap1_eu, ip_addr_jp_ap1_na, ip_addr_jp_ap1_jp], 80)
        tls_conf = {
            "custom_security": {
                "cipher_suites": [
                    "TLS_RSA_WITH_AES_128_CBC_SHA"
                ],
                "max_version": "TLSv1_0",
                "min_version": "TLSv1_0"
            }
        }
        xc_create_loadbalancer(namespace, namespace + "-lb", namespace + "-lb.f5training7.cloud", namespace + "-op", tls_config = tls_conf)

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
            'ip_addr_jp_arc1_eu': ip_addr_jp_ap1_eu,
            'ip_addr_jp_arc1_na': ip_addr_jp_ap1_na,
            'ip_addr_jp_arc1_jp': ip_addr_jp_ap1_jp,
            'namespace': namespace
        })
    }
