"""
Property-based tests for staging deployment automation.

Feature: deploy-staging, Property 5: Staging Deployment Automation
Validates: Requirements 2.1, 4.3
"""
import os
import yaml
from pathlib import Path
from hypothesis import given, strategies as st, settings, HealthCheck
import unittest


@st.composite
def branch_strategy(draw):
    """Generate branch names for deployment testing."""
    branches = ['develop', 'staging', 'feature/test', 'main', 'master']
    return draw(st.sampled_from(branches))


@st.composite
def deployment_config_strategy(draw):
    """Generate deployment configuration scenarios."""
    force_deploy = draw(st.booleans())
    environment = draw(st.sampled_from(['staging', 'production']))
    return {
        'force_deploy': force_deploy,
        'environment': environment
    }


class StagingDeploymentAutomationPropertyTest(unittest.TestCase):
    """
    Property test for staging deployment automation.
    
    **Property 5: Staging Deployment Automation**
    For any code merge to develop/staging branch, the deployment system should 
    automatically trigger staging environment deployment.
    """

    def setUp(self):
        self.workflows_dir = Path(__file__).parent.parent / '.github' / 'workflows'
        self.staging_workflow = self.workflows_dir / 'deploy-staging.yml'

    def test_staging_workflow_exists(self):
        """Test that staging deployment workflow exists."""
        self.assertTrue(self.staging_workflow.exists(), 
                       "Staging deployment workflow should exist")

    @given(branch_name=branch_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.filter_too_much])
    def test_automatic_deployment_trigger_property(self, branch_name):
        """
        Property: For any branch push, staging deployment should trigger 
        automatically only for develop/staging branches.
        """
        with open(self.staging_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        # Get push trigger configuration
        push_config = workflow['on']['push']
        trigger_branches = push_config['branches']

        # Test deployment trigger logic
        should_trigger = branch_name in trigger_branches
        expected_trigger = branch_name in ['develop', 'staging']

        self.assertEqual(should_trigger, expected_trigger,
                        f"Branch {branch_name} trigger behavior should match expected")

    def test_staging_deployment_steps_property(self):
        """
        Property: Staging deployment workflow should contain all required steps
        for automated deployment.
        """
        with open(self.staging_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        # Get deploy job
        deploy_job = workflow['jobs']['deploy']
        steps = deploy_job['steps']
        step_names = [step.get('name', '') for step in steps]

        # Required deployment steps for automation
        required_steps = [
            'Checkout code',
            'Set up Python',
            'Create staging environment file',
            'Pre-deployment validation',
            'Deploy to staging server',
            'Health check'
        ]

        for required_step in required_steps:
            found = any(required_step in step_name for step_name in step_names)
            self.assertTrue(found, f"Should include automated step: {required_step}")

    def test_staging_environment_configuration_property(self):
        """
        Property: Staging deployment should use staging environment configuration.
        """
        with open(self.staging_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        # Deploy job should specify staging environment
        deploy_job = workflow['jobs']['deploy']
        self.assertEqual(deploy_job.get('environment'), 'staging',
                        "Deploy job should use staging environment")

    @given(config=deployment_config_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.filter_too_much])
    def test_deployment_configuration_property(self, config):
        """
        Property: For any deployment configuration, the workflow should handle
        different deployment scenarios appropriately.
        """
        with open(self.staging_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        # Check workflow_dispatch inputs
        workflow_dispatch = workflow['on']['workflow_dispatch']
        inputs = workflow_dispatch['inputs']

        # Should have force_deploy option
        self.assertIn('force_deploy', inputs, "Should support force deployment option")
        
        force_deploy_input = inputs['force_deploy']
        self.assertEqual(force_deploy_input['type'], 'boolean',
                        "Force deploy should be boolean type")
        self.assertEqual(force_deploy_input['default'], 'false',
                        "Force deploy should default to false")

    def test_secrets_integration_property(self):
        """
        Property: Staging deployment should integrate with GitHub Secrets
        for secure configuration management.
        """
        with open(self.staging_workflow, 'r') as f:
            content = f.read()

        # Required secrets for staging deployment
        required_secrets = [
            'DJANGO_SECRET_KEY',
            'STAGING_ALLOWED_HOSTS',
            'STAGING_SSH_PRIVATE_KEY',
            'STAGING_HOST',
            'STAGING_USER'
        ]

        for secret in required_secrets:
            self.assertIn(f'secrets.{secret}', content,
                         f"Should reference secret: {secret}")

    def test_deployment_validation_property(self):
        """
        Property: Staging deployment should include pre-deployment validation
        to ensure code quality before deployment.
        """
        with open(self.staging_workflow, 'r') as f:
            content = f.read()

        # Should include Django checks
        self.assertIn('python manage.py check', content,
                     "Should include Django system check")
        
        # Should include static file validation
        self.assertIn('collectstatic', content,
                     "Should validate static file collection")

    def test_deployment_automation_commands_property(self):
        """
        Property: Staging deployment should use automated deployment commands
        for reliable and consistent deployments.
        """
        with open(self.staging_workflow, 'r') as f:
            content = f.read()

        # Should use rsync for file synchronization
        self.assertIn('rsync', content,
                     "Should use rsync for file synchronization")
        
        # Should restart services automatically
        self.assertIn('systemctl restart', content,
                     "Should restart services automatically")
        
        # Should run database migrations
        self.assertIn('python manage.py migrate', content,
                     "Should run database migrations")

    def test_health_check_automation_property(self):
        """
        Property: Staging deployment should include automated health checks
        to verify deployment success.
        """
        with open(self.staging_workflow, 'r') as f:
            content = f.read()

        # Should include health check step
        self.assertIn('Health check', content,
                     "Should include health check step")
        
        # Should check service status
        self.assertIn('systemctl is-active', content,
                     "Should check service status")

    @given(
        branch=st.sampled_from(['develop', 'staging']),
        event_type=st.sampled_from(['push', 'workflow_dispatch'])
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.filter_too_much])
    def test_trigger_event_combinations_property(self, branch, event_type):
        """
        Property: For any valid branch and event type combination,
        staging deployment should trigger appropriately.
        """
        with open(self.staging_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        # Check if event type is supported
        self.assertIn(event_type, workflow['on'],
                     f"Should support {event_type} events")

        if event_type == 'push':
            # Check if branch is in push triggers
            push_branches = workflow['on']['push']['branches']
            self.assertIn(branch, push_branches,
                         f"Should trigger on push to {branch}")

        if event_type == 'workflow_dispatch':
            # Should allow manual dispatch
            self.assertIn('inputs', workflow['on']['workflow_dispatch'],
                         "Should have workflow dispatch inputs")

    def test_deployment_error_handling_property(self):
        """
        Property: Staging deployment should handle errors gracefully
        and provide appropriate feedback.
        """
        with open(self.staging_workflow, 'r') as f:
            content = f.read()

        # Should have continue-on-error for non-critical steps
        self.assertIn('continue-on-error', content,
                     "Should handle errors gracefully")
        
        # Should have deployment status notification
        self.assertIn('Notify deployment status', content,
                     "Should notify deployment status")
        
        # Should check job status
        self.assertIn('job.status', content,
                     "Should check and report job status")


if __name__ == '__main__':
    unittest.main()