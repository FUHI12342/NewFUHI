"""
AWSコスト監視コマンド（6項目）

Usage:
    python manage.py check_aws_costs [--threshold 50] [--json] [--region ap-northeast-1]
"""
import json
import uuid
from decimal import Decimal

from django.core.management.base import BaseCommand

from booking.models import CostReport


# EC2インスタンスタイプ別の概算月額コスト（USD, ap-northeast-1）
EC2_PRICING = {
    't2.micro': 11.52,
    't2.small': 23.04,
    't2.medium': 46.08,
    't3.micro': 10.37,
    't3.small': 20.74,
    't3.medium': 41.47,
    'm5.large': 96.00,
    'm5.xlarge': 192.00,
    'r5.large': 126.00,
    'c5.large': 85.00,
}


class Command(BaseCommand):
    help = 'AWSリソースのコスト最適化チェックを実行します'

    def add_arguments(self, parser):
        parser.add_argument('--threshold', type=float, default=50.0, help='コスト警告しきい値（USD/月）')
        parser.add_argument('--json', action='store_true', help='JSON形式で結果を出力')
        parser.add_argument('--region', type=str, default='ap-northeast-1', help='AWSリージョン')

    def handle(self, *args, **options):
        run_id = uuid.uuid4()
        threshold = options['threshold']
        output_json = options.get('json', False)
        region = options['region']

        try:
            import boto3
        except ImportError:
            self._save_warn(run_id, 'boto3_missing', 'total',
                            'boto3が未インストールです', 'pip install boto3')
            self.stderr.write(self.style.WARNING('boto3が未インストールのためチェックをスキップします'))
            return

        try:
            session = boto3.Session(region_name=region)
            # 認証テスト
            sts = session.client('sts')
            sts.get_caller_identity()
        except Exception as e:
            self._save_warn(run_id, 'aws_auth_fail', 'total',
                            f'AWS認証失敗: {e}', 'AWS認証情報を確認してください')
            self.stderr.write(self.style.WARNING(f'AWS認証失敗: {e}'))
            return

        results = []
        total_cost = Decimal('0')

        # 1. EC2 instances
        ec2_results, ec2_cost = self._check_ec2(session, run_id, region)
        results.extend(ec2_results)
        total_cost += ec2_cost

        # 2. S3 usage
        results.extend(self._check_s3(session, run_id))

        # 3. EBS volumes
        ebs_results, ebs_cost = self._check_ebs(session, run_id)
        results.extend(ebs_results)
        total_cost += ebs_cost

        # 4. Elastic IPs
        eip_results, eip_cost = self._check_elastic_ips(session, run_id)
        results.extend(eip_results)
        total_cost += eip_cost

        # 5. RDS instances
        rds_results, rds_cost = self._check_rds(session, run_id)
        results.extend(rds_results)
        total_cost += rds_cost

        # 6. Total estimate
        status = 'alert' if total_cost > Decimal(str(threshold)) else 'ok'
        results.append({
            'run_id': run_id,
            'check_name': 'total_estimate',
            'resource_type': 'total',
            'resource_id': '',
            'status': status,
            'estimated_monthly_cost': total_cost,
            'detail': f'推定月額合計: ${total_cost:.2f} (しきい値: ${threshold:.2f})',
            'recommendation': f'月額コストがしきい値(${threshold:.2f})を超えています' if status == 'alert' else '',
        })

        # DB保存
        objects = []
        for r in results:
            objects.append(CostReport(
                run_id=r['run_id'],
                check_name=r['check_name'],
                resource_type=r['resource_type'],
                resource_id=r.get('resource_id', ''),
                status=r['status'],
                estimated_monthly_cost=r['estimated_monthly_cost'],
                detail=r.get('detail', ''),
                recommendation=r.get('recommendation', ''),
            ))
        CostReport.objects.bulk_create(objects)

        # 出力
        if output_json:
            output = []
            for r in results:
                row = dict(r)
                row['run_id'] = str(row['run_id'])
                row['estimated_monthly_cost'] = str(row['estimated_monthly_cost'])
                output.append(row)
            self.stdout.write(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            self.stdout.write(f'\n=== AWSコストレポート (run_id: {run_id}) ===\n')
            for r in results:
                icon = {'ok': 'OK', 'warn': 'WARN', 'alert': 'ALERT'}[r['status']]
                line = f'[{icon}] {r["check_name"]} ({r["resource_type"]}): ${r["estimated_monthly_cost"]:.2f} - {r["detail"]}'
                if r['status'] == 'alert':
                    self.stdout.write(self.style.ERROR(line))
                elif r['status'] == 'warn':
                    self.stdout.write(self.style.WARNING(line))
                else:
                    self.stdout.write(self.style.SUCCESS(line))
            self.stdout.write(f'\n推定月額合計: ${total_cost:.2f}\n')

    def _save_warn(self, run_id, check_name, resource_type, detail, recommendation):
        CostReport.objects.create(
            run_id=run_id,
            check_name=check_name,
            resource_type=resource_type,
            resource_id='',
            status='warn',
            estimated_monthly_cost=0,
            detail=detail,
            recommendation=recommendation,
        )

    def _check_ec2(self, session, run_id, region):
        results = []
        total = Decimal('0')
        try:
            ec2 = session.client('ec2')
            cw = session.client('cloudwatch')
            instances = ec2.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
            )
            for reservation in instances.get('Reservations', []):
                for inst in reservation.get('Instances', []):
                    inst_id = inst['InstanceId']
                    inst_type = inst.get('InstanceType', 'unknown')
                    cost = Decimal(str(EC2_PRICING.get(inst_type, 50.0)))
                    total += cost

                    # CPU utilization check
                    status = 'ok'
                    detail = f'{inst_type} (稼働中)'
                    recommendation = ''
                    try:
                        from datetime import datetime, timedelta, timezone as tz
                        end = datetime.now(tz.utc)
                        start = end - timedelta(hours=24)
                        cpu_stats = cw.get_metric_statistics(
                            Namespace='AWS/EC2',
                            MetricName='CPUUtilization',
                            Dimensions=[{'Name': 'InstanceId', 'Value': inst_id}],
                            StartTime=start,
                            EndTime=end,
                            Period=3600,
                            Statistics=['Average'],
                        )
                        datapoints = cpu_stats.get('Datapoints', [])
                        if datapoints:
                            avg_cpu = sum(d['Average'] for d in datapoints) / len(datapoints)
                            detail = f'{inst_type} (CPU平均: {avg_cpu:.1f}%)'
                            if avg_cpu < 10:
                                status = 'warn'
                                recommendation = f'CPU使用率が低い({avg_cpu:.1f}%)ためインスタンス縮小を検討'
                    except Exception:
                        pass

                    results.append({
                        'run_id': run_id,
                        'check_name': 'ec2_instances',
                        'resource_type': 'ec2',
                        'resource_id': inst_id,
                        'status': status,
                        'estimated_monthly_cost': cost,
                        'detail': detail,
                        'recommendation': recommendation,
                    })
        except Exception as e:
            results.append({
                'run_id': run_id,
                'check_name': 'ec2_instances',
                'resource_type': 'ec2',
                'resource_id': '',
                'status': 'warn',
                'estimated_monthly_cost': Decimal('0'),
                'detail': f'EC2チェック失敗: {e}',
                'recommendation': '',
            })
        return results, total

    def _check_s3(self, session, run_id):
        results = []
        try:
            s3 = session.client('s3')
            buckets = s3.list_buckets().get('Buckets', [])
            for bucket in buckets:
                name = bucket['Name']
                has_lifecycle = False
                try:
                    s3.get_bucket_lifecycle_configuration(Bucket=name)
                    has_lifecycle = True
                except Exception:
                    pass

                status = 'ok' if has_lifecycle else 'warn'
                recommendation = '' if has_lifecycle else 'ライフサイクルポリシーの設定を推奨'

                results.append({
                    'run_id': run_id,
                    'check_name': 's3_usage',
                    'resource_type': 's3',
                    'resource_id': name,
                    'status': status,
                    'estimated_monthly_cost': Decimal('0'),
                    'detail': f'バケット: {name} (ライフサイクル: {"あり" if has_lifecycle else "なし"})',
                    'recommendation': recommendation,
                })
        except Exception as e:
            results.append({
                'run_id': run_id,
                'check_name': 's3_usage',
                'resource_type': 's3',
                'resource_id': '',
                'status': 'warn',
                'estimated_monthly_cost': Decimal('0'),
                'detail': f'S3チェック失敗: {e}',
                'recommendation': '',
            })
        return results

    def _check_ebs(self, session, run_id):
        results = []
        total = Decimal('0')
        try:
            ec2 = session.client('ec2')
            volumes = ec2.describe_volumes(
                Filters=[{'Name': 'status', 'Values': ['available']}]
            )
            for vol in volumes.get('Volumes', []):
                vol_id = vol['VolumeId']
                size = vol.get('Size', 0)
                cost = Decimal(str(size * 0.12))  # gp2 approximate
                total += cost
                results.append({
                    'run_id': run_id,
                    'check_name': 'ebs_volumes',
                    'resource_type': 'ebs',
                    'resource_id': vol_id,
                    'status': 'warn',
                    'estimated_monthly_cost': cost,
                    'detail': f'未アタッチEBS: {vol_id} ({size}GB)',
                    'recommendation': '不要であれば削除してコスト削減',
                })
        except Exception as e:
            results.append({
                'run_id': run_id,
                'check_name': 'ebs_volumes',
                'resource_type': 'ebs',
                'resource_id': '',
                'status': 'warn',
                'estimated_monthly_cost': Decimal('0'),
                'detail': f'EBSチェック失敗: {e}',
                'recommendation': '',
            })
        return results, total

    def _check_elastic_ips(self, session, run_id):
        results = []
        total = Decimal('0')
        try:
            ec2 = session.client('ec2')
            addresses = ec2.describe_addresses()
            for addr in addresses.get('Addresses', []):
                if not addr.get('AssociationId'):
                    eip = addr.get('PublicIp', 'unknown')
                    cost = Decimal('3.65')
                    total += cost
                    results.append({
                        'run_id': run_id,
                        'check_name': 'elastic_ips',
                        'resource_type': 'eip',
                        'resource_id': eip,
                        'status': 'warn',
                        'estimated_monthly_cost': cost,
                        'detail': f'未使用Elastic IP: {eip} ($3.65/月)',
                        'recommendation': '使用していなければリリースしてください',
                    })
        except Exception as e:
            results.append({
                'run_id': run_id,
                'check_name': 'elastic_ips',
                'resource_type': 'eip',
                'resource_id': '',
                'status': 'warn',
                'estimated_monthly_cost': Decimal('0'),
                'detail': f'Elastic IPチェック失敗: {e}',
                'recommendation': '',
            })
        return results, total

    def _check_rds(self, session, run_id):
        results = []
        total = Decimal('0')
        try:
            rds = session.client('rds')
            instances = rds.describe_db_instances()
            for db in instances.get('DBInstances', []):
                db_id = db['DBInstanceIdentifier']
                db_class = db.get('DBInstanceClass', 'unknown')
                status = db.get('DBInstanceStatus', 'unknown')
                cost = Decimal('50.00')  # rough estimate
                total += cost
                results.append({
                    'run_id': run_id,
                    'check_name': 'rds_instances',
                    'resource_type': 'rds',
                    'resource_id': db_id,
                    'status': 'ok' if status == 'available' else 'warn',
                    'estimated_monthly_cost': cost,
                    'detail': f'RDS: {db_id} ({db_class}, {status})',
                    'recommendation': '',
                })
        except Exception as e:
            results.append({
                'run_id': run_id,
                'check_name': 'rds_instances',
                'resource_type': 'rds',
                'resource_id': '',
                'status': 'warn',
                'estimated_monthly_cost': Decimal('0'),
                'detail': f'RDSチェック失敗: {e}',
                'recommendation': '',
            })
        return results, total
