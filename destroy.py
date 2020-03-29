import argparse
import json
import logging
import sys
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)
Region = ''


def delete_stack(stack_name, Region, ACCESS_KEY, SECRET_KEY):
    """

    Sends a delete stack request and monitors the progress of the deletion process by calling describe_stacks

    :param stack_name:
    :param Region:
    :return:
    """
    cf_client = boto3.client('cloudformation',
                             region_name=Region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)

    #
    # Need to use the StackId when calling describe stacks as DELETE_COMPLETE is never returned using stack names
    #
    try:
        stack_data = cf_client.describe_stacks(StackName=stack_name)
        stack_id = stack_data['Stacks'][0]['StackId']
        response = cf_client.delete_stack(StackName=stack_id)

        if 'ResponseMetadata' in response and response['ResponseMetadata']['HTTPStatusCode'] < 300:
            logger.info("Got response: {0}".format(response))

            while True:
                try:
                    stack_data = cf_client.describe_stacks(StackName=stack_id)

                    if stack_data['Stacks'][0]['StackStatus'] == 'ROLLBACK_IN_PROGRESS':
                        print('Stack is rolling back - check the event logs')
                        time.sleep(30)
                        continue
                    elif stack_data['Stacks'][0]['StackStatus'] == 'DELETE_IN_PROGRESS':
                        print('Stack still deleting')
                        time.sleep(30)
                        continue
                    elif stack_data['Stacks'][0]['StackStatus'] == 'DELETE_FAILED':
                        print('Stack has failed to delete check your console')
                        return False
                    elif stack_data['Stacks'][0]['StackStatus'] == 'ROLLBACK_FAILED':
                        print('Stack has failed to rollback check your console')
                        return False
                    elif stack_data['Stacks'][0]['StackStatus'] == 'DELETE_COMPLETE':
                        print('Stack has been deleted')
                        return True
                    else:
                        print('Please check the stack deletion status in your AWS console')
                        return False
                except ClientError:
                    print('Unable to find stack {}'.format(stack_name))
                    return False
                except Exception as e:
                    logger.info('Got exception {}'.format(e))
                    return False

        else:
            logger.info("There was an Unexpected error. response: {0}".format(response))
            return False

    except ClientError as error:
        print('Got exception {}'.format(error))
    except Exception as e:
        print('Got exception {}'.format(e))


def delete_bucket(s3bucket_name, Region, ACCESS_KEY, SECRET_KEY):
    """
    Deletes the S3 bucket used for stack deployment and firewall bootstrap
    :param s3bucket_name:
    :param Region:
    :param ACCESS_KEY:
    :param SECRET_KEY:
    :return:
    """
    s3 = boto3.resource('s3',
                        region_name=Region,
                        aws_access_key_id=ACCESS_KEY,
                        aws_secret_access_key=SECRET_KEY)

    bucket = s3.Bucket(s3bucket_name)
    response = bucket.objects.all().delete()
    bucket.delete()
    if 'ResponseMetadata' in response and response[0]['ResponseMetadata']['HTTPStatusCode'] < 300:
        print('Got response to S3 bucket delete all {}'.format(response))
        return True
    else:
        return False


def main():
    """
    First deletes the cloudformation stack and then deletes the S3 bucket used in the deployment
    :return:
    """
    global Region
    """
    Input arguments
    
    """
    parser = argparse.ArgumentParser(description='Get Parameters')
    parser.add_argument('-k', '--aws_access_key', help='AWS Key', required=True)
    parser.add_argument('-s', '--aws_secret_key', help='AWS Secret', required=True)

    args = parser.parse_args()

    ACCESS_KEY = args.aws_access_key
    SECRET_KEY = args.aws_secret_key


    try:
        with open('deployment_data.json', 'r') as data:

            config_dict = json.load(data)
            aws_region = config_dict['aws_region']
            stack_name = config_dict['stack_name']
            s3bucket_name = config_dict['s3bucket_name']
    except FileNotFoundError:
        print('File no longer exists')
    except Exception as e:
        print('Got exception {}'.format(e))
        sys.exit("Could not find deployment config file 'deployment_data.json'")

    print('Deleting Stack {}'.format(stack_name))

    if delete_stack(stack_name, aws_region, ACCESS_KEY, SECRET_KEY):
        print('Deleted Stack {}'.format(stack_name))
        print('Deleting S3 Bucket {}'.format(s3bucket_name))
        if delete_bucket(s3bucket_name, aws_region, ACCESS_KEY, SECRET_KEY):
            print('Deleted S3 Bucket {}'.format(s3bucket_name))
    else:
        print('There was a problem deteting the stack {}'.format(stack_name))


if __name__ == '__main__':
    main()
