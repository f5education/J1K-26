def instructions():
    try:
        # namespace = xc_create_user_and_namespace(create_namespace = False)
        # namespace = "Leasuresuit-Larry"
        namespace = xc_create_namespace(name_only = True)
        # tenant_api = xc_create_api_token()
        _, ip_addr_jp_arc1_jp = ec2_start_instance("jp-arc1-jp")
        
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
            'ip_addr_jp_arc1_jp': ip_addr_jp_arc1_jp
            # 'tenant_api': tenant_api
        })
    }
