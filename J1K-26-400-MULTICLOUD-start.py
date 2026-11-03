def instructions():
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            # Submit tasks
            futures_jp_ap2_eu = executor.submit(ec2_start_instance, "jp-ap2-eu")
            futures_jp_sm1_eu = executor.submit(ec2_start_instance, "jp-sm1-eu")
            futures_jp_ap2_jp = executor.submit(ec2_start_instance, "jp-ap2-jp")
            futures_jp_sm1_jp = executor.submit(ec2_start_instance, "jp-sm1-jp")

            # Retrieve results
            _, ip_addr_jp_ap2_eu = futures_jp_ap2_eu.result()
            _, ip_addr_jp_sm1_eu = futures_jp_sm1_eu.result()
            _, ip_addr_jp_ap2_jp = futures_jp_ap2_jp.result()
            _, ip_addr_jp_sm1_jp = futures_jp_sm1_jp.result()
        
        namespace = xc_create_user_and_namespace()
        
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
