#!/usr/bin/env python3

from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import argparse
import boto3
import ipaddress
import logging
import requests
import time

class aws_route53_ddns:
    def __init__(self, profile, zone_id, hostname):
        self.profile = profile
        self.zone_id = zone_id
        self.hostname = hostname
        self.client = self._get_route53_client()
        self.logger = self._get_logger()

    def _get_route53_client(self):
        session = boto3.Session(profile_name=self.profile)
        return session.client('route53')

    def _get_logger(self):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)

        log_file = f'{self.hostname}_aws_route53_ddns.log'
        file_handler = logging.FileHandler(log_file)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='[%d/%b/%Y:%H:%M:%S %z]')
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

        return logger

    def _request(self, url):

        adapter = HTTPAdapter(
            max_retries=
            Retry(
                total = 5,
                backoff_factor = 1,
                status_forcelist = [500, 502, 503, 504])
        )
        
        http = requests.Session()
        http.mount("https://", adapter)
        http.mount("http://", adapter)
        return http.get(url)
    
    def _get_public_ip(self, type: str):

        response = None

        if type in ["A"]:
            response = self._request(self, 'https://api.ipify.org')
        if type in ["AAAA"]:
            response = self._request(self, 'https://api64.ipify.org')
            
        try:
            ipaddress.ip_address(getattr(response, "text", ""))
            return [response.text]
        except ValueError:
            self.logger.error(f'[ERROR] - _get_public_ip(self, type: str): - No IP found in <response.text> = {getattr(response, "text", "")}!')
        except:
            self.logger.error(f'[ERROR] - _get_public_ip(self, {type}): Invalid type!')

        return [""]

    def _get_route53_hosted_zone_records(self, type: str):
        
        records = []
        
        if type in ["A", "AAAA"]:
            
            response = self.client.list_resource_record_sets(
                HostedZoneId=self.zone_id,
                StartRecordName=f'{self.hostname}.',
                StartRecordType=type,
            )
            
            if 'ResourceRecordSets' in response:
                
                hosted_zone_records = response['ResourceRecordSets'][0]
                
                if hosted_zone_records['Name'] == f'{self.hostname}.' and hosted_zone_records['Type'] == type:
                    
                    records = [record['Value'] for record in hosted_zone_records['ResourceRecords']]
            
            else:
                
                self.logger.error('[ERROR] _get_a_records(self): No ResourceRecordSets in response!')

        else:
            
            self.logger.error(f'[ERROR] - _get_route53_hosted_zone_records(self, {type}) not in ["A", "AAAA"]')

        return records
    
    def _set_route53_hosted_zone_records(self, type: str):

        if type in ["A", "AAAA"]:
        
            records = self._get_route53_hosted_zone_records(self, type)
            addresses = self._get_public_ip(self, type)

            if records:
                new_addresses = [str(address) for address in addresses if str(address) not in records]

                if new_addresses:
                    self.logger.info(f'[INFO] _set_route53_hosted_zone_records(self, {type}): New records found: {new_addresses}')
                else:
                    self.logger.info(f'[INFO] _set_route53_hosted_zone_records(self, {type}): No new records found.')
                    return

                changes = []
                for address in new_addresses:
                    change = {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': f'{self.hostname}.',
                            'Type': type,
                            'TTL': 300,
                            'ResourceRecords': [
                                {
                                    'Value': address
                                }
                            ]
                        }
                    }
                    changes.append(change)

            else:
                changes = [
                    {
                        'Action': 'CREATE',
                        'ResourceRecordSet': {
                            'Name': f'{self.hostname}.',
                            'Type': type,
                            'TTL': 300,
                            'ResourceRecords': [
                                {
                                    'Value': str(address)
                                } for address in addresses
                            ]
                        }
                    }
                ]
            
            '''
            response = self.client.change_resource_record_sets(
                HostedZoneId=self.zone_id,
                ChangeBatch={
                    'Changes': changes
                }
            )
            '''

            self.logger.info(f'{changes}')

            return
    
    def update_route53_records(self):
        self._set_route53_hosted_zone_records(self, "A")
        self._set_route53_hosted_zone_records(self, "AAAA")
        return

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='A simple, A/AAAA Python based Route 53 hosted zone record update tool for locally hosted resources with dynamic IP addresses.')
    parser.add_argument('-p', '--profile', required=True, help='AWS CLI profile name')
    parser.add_argument('-z', '--zone-id', required=True, help='Route 53 hosted zone ID')
    parser.add_argument('-h', '--hostname', required=True, help='Hostname as FQDN, i.e. host.your.domain, wildcards * included')
    args = parser.parse_args()

    instance = aws_route53_ddns(args.profile, args.zone_id, args.hostname, args.verbose)

    instance.update_route53_records()