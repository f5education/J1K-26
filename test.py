def instructions():
    debug()
    response = "Hello world -- these instructions came from GitHub"
    print(response)
    return {
        'statusCode': 200,
        'body': json.dumps({
            'content': response
        })
    }
