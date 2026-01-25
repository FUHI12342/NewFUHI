"""
Property-based tests for CI pipeline triggers.

Feature: deploy-staging, Property 4: CI Pipeline Trigger
Validates: Requirements 1.5, 4.1
"""
import os
import yaml
from pathlib import Path
from hypothesis import given, strategies as st, settings, HealthCheck
import unittest


@st.composite
def github_event_strategy(draw):
    """Generate GitHub event configurations."""
    events = ['pull_request', 'push', 'workflow_dispatch']
    return draw(st.sampled_from(events))


@st.composite
def branch_strategy(draw):
    """Generate branch name configurations."""
    branches = ['main', 'master', 'develop', 'staging', 'feature/test']
    return draw(st.sampled_from(branches))


class CIPipelineTriggerPropertyTest(unittest.TestCase):
    """
    Property test for CI pipeline triggers.
    
    **Property 4: CI Pipeline Trigger**
    For any pull request created, the CI pipeline should automatically trigger 
    validation checks including linting, type checking, and tests.
    """

    def setUp(self):
        self.workflows_dir = Path(__file__).parent.parent / '.github' / 'workflows'
        self.pr_workflow = self.workflows_dir / 'pr-validation.yml'
        self.staging_workflow = self.workflows_dir / 'deploy-staging.yml'
        self.production_workflow = self.workflows_dir / 'deploy-production.yml'

    def test_workflow_files_exist(self):
        """Test that all required workflow files exist."""
        self.assertTrue(self.pr_workflow.exists(), "PR validation workflow should exist")
        self.assertTrue(self.staging_workflow.exists(), "Staging deployment workflow should exist")
        self.assertTrue(self.production_workflow.exists(), "Production deployment workflow should exist")

    def test_pr_workflow_triggers(self):
        """Test that PR workflow triggers on correct events."""
        with open(self.pr_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        # Should trigger on pull requests
        self.assertIn('pull_request', workflow['on'], "Should trigger on pull_request events")
        
        # Should trigger on push to specific branches
        self.assertIn('push', workflow['on'], "Should trigger on push events")
        
        # Check target branches for pull requests
        pr_branches = workflow['on']['pull_request']['branches']
        expected_branches = ['main', 'master', 'develop', 'staging']
        for branch in expected_branches:
            self.assertIn(branch, pr_branches, f"Should trigger on PR to {branch}")

    def test_staging_workflow_triggers(self):
        """Test that staging workflow triggers on correct events."""
        with open(self.staging_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        # Should trigger on push to develop/staging
        self.assertIn('push', workflow['on'], "Should trigger on push events")
        push_branches = workflow['on']['push']['branches']
        self.assertIn('develop', push_branches, "Should trigger on push to develop")
        self.assertIn('staging', push_branches, "Should trigger on push to staging")
        
        # Should allow manual dispatch
        self.assertIn('workflow_dispatch', workflow['on'], "Should allow manual dispatch")

    def test_production_workflow_triggers(self):
        """Test that production workflow has manual-only triggers."""
        with open(self.production_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        # Should only trigger manually or on release tags
        self.assertIn('workflow_dispatch', workflow['on'], "Should allow manual dispatch")
        self.assertIn('push', workflow['on'], "Should trigger on tag push")
        
        # Check that it triggers on release tags
        if 'tags' in workflow['on']['push']:
            tags = workflow['on']['push']['tags']
            self.assertIn('release-*', tags, "Should trigger on release-* tags")

    @given(
        event_type=github_event_strategy(),
        branch_name=branch_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.filter_too_much])
    def test_workflow_trigger_logic_property(self, event_type, branch_name):
        """
        Property: For any GitHub event and branch combination,
        the appropriate workflow should be triggered based on the configuration.
        """
        with open(self.pr_workflow, 'r') as f:
            pr_workflow = yaml.safe_load(f)
        
        with open(self.staging_workflow, 'r') as f:
            staging_workflow = yaml.safe_load(f)

        # Test PR workflow trigger logic
        if event_type == 'pull_request':
            pr_branches = pr_workflow['on']['pull_request']['branches']
            should_trigger_pr = branch_name in pr_branches
            
            # Verify the logic is consistent
            if branch_name in ['main', 'master', 'develop', 'staging']:
                self.assertTrue(should_trigger_pr, 
                    f"PR workflow should trigger for {branch_name}")

        # Test staging workflow trigger logic
        if event_type == 'push':
            staging_branches = staging_workflow['on']['push']['branches']
            should_trigger_staging = branch_name in staging_branches
            
            # Verify the logic is consistent
            if branch_name in ['develop', 'staging']:
                self.assertTrue(should_trigger_staging,
                    f"Staging workflow should trigger for {branch_name}")

    def test_pr_workflow_validation_steps(self):
        """Test that PR workflow includes all required validation steps."""
        with open(self.pr_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        # Get the validate job
        validate_job = workflow['jobs']['validate']
        step_names = [step.get('name', '') for step in validate_job['steps']]

        # Required validation steps
        required_steps = [
            'Lint with flake8',
            'Check code formatting with black',
            'Check import sorting with isort',
            'Type checking with mypy',
            'Django system check',
            'Run migrations check',
            'Collect static files',
            'Run tests with coverage'
        ]

        for required_step in required_steps:
            found = any(required_step in step_name for step_name in step_names)
            self.assertTrue(found, f"Should include validation step: {required_step}")

    def test_staging_workflow_deployment_steps(self):
        """Test that staging workflow includes all required deployment steps."""
        with open(self.staging_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        # Get the deploy job
        deploy_job = workflow['jobs']['deploy']
        step_names = [step.get('name', '') for step in deploy_job['steps']]

        # Required deployment steps
        required_steps = [
            'Pre-deployment validation',
            'Setup SSH key',
            'Deploy to staging server',
            'Health check'
        ]

        for required_step in required_steps:
            found = any(required_step in step_name for step_name in step_names)
            self.assertTrue(found, f"Should include deployment step: {required_step}")

    def test_production_workflow_security(self):
        """Test that production workflow has proper security measures."""
        with open(self.production_workflow, 'r') as f:
            workflow = yaml.safe_load(f)

        # Should have manual approval step
        jobs = workflow['jobs']
        
        # Check for validation input job
        self.assertIn('validate-input', jobs, "Should validate input for production deployment")
        
        # Check for pre-deployment checks
        self.assertIn('pre-deployment-checks', jobs, "Should have pre-deployment checks")
        
        # Check for production environment requirement
        deploy_job = jobs.get('deploy-production', {})
        self.assertEqual(deploy_job.get('environment'), 'production', 
                        "Should require production environment")

    @given(workflow_name=st.sampled_from(['pr-validation.yml', 'deploy-staging.yml', 'deploy-production.yml']))
    @settings(max_examples=10)
    def test_workflow_yaml_validity_property(self, workflow_name):
        """
        Property: For any workflow file, it should be valid YAML
        and contain required GitHub Actions structure.
        """
        workflow_path = self.workflows_dir / workflow_name
        
        # Should be valid YAML
        with open(workflow_path, 'r') as f:
            try:
                workflow = yaml.safe_load(f)
            except yaml.YAMLError as e:
                self.fail(f"Workflow {workflow_name} has invalid YAML: {e}")

        # Should have required top-level keys
        required_keys = ['name', 'on', 'jobs']
        for key in required_keys:
            self.assertIn(key, workflow, f"Workflow {workflow_name} should have {key}")

        # Should have at least one job
        self.assertGreater(len(workflow['jobs']), 0, 
                          f"Workflow {workflow_name} should have at least one job")

    def test_environment_secrets_configuration(self):
        """Test that workflows reference appropriate secrets."""
        with open(self.staging_workflow, 'r') as f:
            staging_content = f.read()

        with open(self.production_workflow, 'r') as f:
            production_content = f.read()

        # Staging should reference staging secrets
        staging_secrets = [
            'DJANGO_SECRET_KEY',
            'STAGING_ALLOWED_HOSTS',
            'STAGING_SSH_PRIVATE_KEY',
            'STAGING_HOST'
        ]

        for secret in staging_secrets:
            self.assertIn(f'secrets.{secret}', staging_content,
                         f"Staging workflow should reference {secret}")

        # Production should reference production secrets
        production_secrets = [
            'PRODUCTION_DJANGO_SECRET_KEY',
            'PRODUCTION_ALLOWED_HOSTS',
            'PRODUCTION_DATABASE_URL'
        ]

        for secret in production_secrets:
            self.assertIn(f'secrets.{secret}', production_content,
                         f"Production workflow should reference {secret}")


if __name__ == '__main__':
    unittest.main()