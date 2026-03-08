"""Tests for check_aws_costs management command."""
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from django.core.management import call_command
from io import StringIO

from booking.models import CostReport


class TestCheckAWSCostsCommand:
    """Tests for the check_aws_costs management command."""

    @pytest.mark.django_db
    def test_handles_missing_boto3(self):
        """Command handles missing boto3 gracefully."""
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'boto3':
                raise ImportError('No module named boto3')
            return real_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            stderr = StringIO()
            call_command('check_aws_costs', stderr=stderr)
            # Should create a warn report for boto3_missing
            report = CostReport.objects.filter(check_name='boto3_missing')
            assert report.exists()

    @pytest.mark.django_db
    def test_handles_auth_failure(self):
        """Command handles AWS authentication failure."""
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = Exception('Access Denied')
        mock_session.client.return_value = mock_sts

        with patch('boto3.Session', return_value=mock_session):
            stderr = StringIO()
            call_command('check_aws_costs', stderr=stderr)
            report = CostReport.objects.filter(check_name='aws_auth_fail')
            assert report.exists()

    @pytest.mark.django_db
    def test_with_mocked_boto3_session(self):
        """Command runs successfully with mocked AWS session."""
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456'}

        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.return_value = {'Reservations': []}
        mock_ec2.describe_volumes.return_value = {'Volumes': []}
        mock_ec2.describe_addresses.return_value = {'Addresses': []}

        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {'Buckets': []}

        mock_rds = MagicMock()
        mock_rds.describe_db_instances.return_value = {'DBInstances': []}

        mock_cw = MagicMock()

        def client_factory(service):
            return {
                'sts': mock_sts,
                'ec2': mock_ec2,
                's3': mock_s3,
                'rds': mock_rds,
                'cloudwatch': mock_cw,
            }[service]

        mock_session.client.side_effect = client_factory

        with patch('boto3.Session', return_value=mock_session):
            call_command('check_aws_costs')
            # Should have at least the total_estimate report
            assert CostReport.objects.filter(check_name='total_estimate').exists()

    @pytest.mark.django_db
    def test_total_estimate_status_ok_below_threshold(self):
        """Total estimate is 'ok' when cost is below threshold."""
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {'Account': '123'}

        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.return_value = {'Reservations': []}
        mock_ec2.describe_volumes.return_value = {'Volumes': []}
        mock_ec2.describe_addresses.return_value = {'Addresses': []}
        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {'Buckets': []}
        mock_rds = MagicMock()
        mock_rds.describe_db_instances.return_value = {'DBInstances': []}

        def client_factory(service):
            return {'sts': mock_sts, 'ec2': mock_ec2, 's3': mock_s3,
                    'rds': mock_rds, 'cloudwatch': MagicMock()}[service]

        mock_session.client.side_effect = client_factory

        with patch('boto3.Session', return_value=mock_session):
            call_command('check_aws_costs', '--threshold', '100')
            report = CostReport.objects.get(check_name='total_estimate')
            assert report.status == 'ok'

    @pytest.mark.django_db
    def test_ec2_instance_detected(self):
        """Command detects running EC2 instances."""
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {'Account': '123'}

        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-12345',
                    'InstanceType': 't3.micro',
                }]
            }]
        }
        mock_ec2.describe_volumes.return_value = {'Volumes': []}
        mock_ec2.describe_addresses.return_value = {'Addresses': []}

        mock_cw = MagicMock()
        mock_cw.get_metric_statistics.return_value = {'Datapoints': []}

        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {'Buckets': []}
        mock_rds = MagicMock()
        mock_rds.describe_db_instances.return_value = {'DBInstances': []}

        def client_factory(service):
            return {'sts': mock_sts, 'ec2': mock_ec2, 's3': mock_s3,
                    'rds': mock_rds, 'cloudwatch': mock_cw}[service]

        mock_session.client.side_effect = client_factory

        with patch('boto3.Session', return_value=mock_session):
            call_command('check_aws_costs')
            report = CostReport.objects.filter(
                check_name='ec2_instances', resource_id='i-12345',
            )
            assert report.exists()

    @pytest.mark.django_db
    def test_json_output(self):
        """Command outputs valid JSON when --json flag is used."""
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {'Account': '123'}

        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.return_value = {'Reservations': []}
        mock_ec2.describe_volumes.return_value = {'Volumes': []}
        mock_ec2.describe_addresses.return_value = {'Addresses': []}
        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {'Buckets': []}
        mock_rds = MagicMock()
        mock_rds.describe_db_instances.return_value = {'DBInstances': []}

        def client_factory(service):
            return {'sts': mock_sts, 'ec2': mock_ec2, 's3': mock_s3,
                    'rds': mock_rds, 'cloudwatch': MagicMock()}[service]

        mock_session.client.side_effect = client_factory

        stdout = StringIO()
        with patch('boto3.Session', return_value=mock_session):
            call_command('check_aws_costs', '--json', stdout=stdout)
        import json
        output = json.loads(stdout.getvalue())
        assert isinstance(output, list)

    @pytest.mark.django_db
    def test_unattached_ebs_volume_warning(self):
        """Command warns about unattached EBS volumes."""
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {'Account': '123'}

        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.return_value = {'Reservations': []}
        mock_ec2.describe_volumes.return_value = {
            'Volumes': [{'VolumeId': 'vol-abc', 'Size': 100}]
        }
        mock_ec2.describe_addresses.return_value = {'Addresses': []}
        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {'Buckets': []}
        mock_rds = MagicMock()
        mock_rds.describe_db_instances.return_value = {'DBInstances': []}

        def client_factory(service):
            return {'sts': mock_sts, 'ec2': mock_ec2, 's3': mock_s3,
                    'rds': mock_rds, 'cloudwatch': MagicMock()}[service]

        mock_session.client.side_effect = client_factory

        with patch('boto3.Session', return_value=mock_session):
            call_command('check_aws_costs')
            report = CostReport.objects.filter(
                check_name='ebs_volumes', resource_id='vol-abc',
            )
            assert report.exists()
            assert report.first().status == 'warn'

    @pytest.mark.django_db
    def test_unused_elastic_ip_warning(self):
        """Command warns about unused Elastic IPs."""
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {'Account': '123'}

        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.return_value = {'Reservations': []}
        mock_ec2.describe_volumes.return_value = {'Volumes': []}
        mock_ec2.describe_addresses.return_value = {
            'Addresses': [{'PublicIp': '1.2.3.4'}]  # no AssociationId
        }
        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {'Buckets': []}
        mock_rds = MagicMock()
        mock_rds.describe_db_instances.return_value = {'DBInstances': []}

        def client_factory(service):
            return {'sts': mock_sts, 'ec2': mock_ec2, 's3': mock_s3,
                    'rds': mock_rds, 'cloudwatch': MagicMock()}[service]

        mock_session.client.side_effect = client_factory

        with patch('boto3.Session', return_value=mock_session):
            call_command('check_aws_costs')
            report = CostReport.objects.filter(
                check_name='elastic_ips', resource_id='1.2.3.4',
            )
            assert report.exists()
            assert report.first().status == 'warn'
