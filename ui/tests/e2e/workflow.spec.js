import { test, expect } from '@playwright/test';

/**
 * E2E tests for Workflow Demo UI
 * 
 * Tests the complete flow: UI → API → Worker → DB → SSE → UI
 * 
 * Prerequisites (run before tests):
 * - make up (Postgres + Redis)
 * - make api (FastAPI server on :8000)
 * - make worker (workflow worker consuming queue)
 * - npm run dev (UI on :5173, managed by Playwright webServer config)
 */

test.describe('Workflow Demo UI - End-to-End', () => {
  
  test('should load UI and display main screen', async ({ page }) => {
    await page.goto('/');
    
    // Verify main UI elements
    await expect(page.getByRole('heading', { name: 'Notebook LM Agent' })).toBeVisible();
    await expect(page.getByText('Interactive workflow exploration')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Live Updates' })).toBeVisible();
    await expect(page.getByTestId('agent-state')).toBeVisible();
  });

  test('should create workflow and observe live progress to completion', async ({ page }) => {
    await page.goto('/');
    
    // Fill in the prompt textarea
    await page.getByTestId('prompt-input').fill('Generate artifacts for testing');
    
    // Click create button (now labeled "Start")
    await page.getByTestId('submit-workflow-btn').click();
    
    // Wait for workflow ID to appear (indicates creation succeeded)
    await expect(page.getByTestId('workflow-id')).toBeVisible({ timeout: 10000 });
    const workflowIdText = await page.getByTestId('workflow-id').textContent();
    expect(workflowIdText).toMatch(/wf_[a-z0-9]+/);
    
    // Extract workflow ID for later
    const workflowId = workflowIdText;
    
    // Verify status appears and changes
    await expect(page.getByTestId('workflow-status')).toBeVisible({ timeout: 5000 });
    
    // Wait for at least one event in event stream
    await expect(page.getByTestId('event-entry').first()).toBeVisible({ timeout: 10000 });
    
    // Wait for workflow to reach terminal state (COMPLETED or FAILED)
    await expect(page.getByTestId('workflow-status')).toHaveText(/COMPLETED|FAILED/, { timeout: 30000 });
    
    // Verify final state
    const finalStatus = await page.getByTestId('workflow-status').textContent();
    expect(['COMPLETED', 'FAILED']).toContain(finalStatus);
    
    // If COMPLETED, verify artifacts appear
    if (finalStatus === 'COMPLETED') {
      await expect(page.getByTestId('workflow-artifacts')).toBeVisible({ timeout: 5000 });
    }
    
    // Verify event stream has multiple entries
    const eventCount = await page.getByTestId('event-entry').count();
    expect(eventCount).toBeGreaterThan(1);
  });

  test('should reload page and replay workflow events', async ({ page }) => {
    await page.goto('/');
    
    // Create a workflow first
    await page.getByTestId('prompt-input').fill('Test workflow replay');
    await page.getByTestId('submit-workflow-btn').click();
    await expect(page.getByTestId('workflow-id')).toBeVisible({ timeout: 10000 });
    
    const workflowIdText = await page.getByTestId('workflow-id').textContent();
    const workflowId = workflowIdText;
    
    // Wait for workflow to reach terminal state
    await expect(page.getByTestId('workflow-status')).toHaveText(/COMPLETED|FAILED/, { timeout: 30000 });
    
    // Get event count before reload
    const eventCountBefore = await page.getByTestId('event-entry').count();
    expect(eventCountBefore).toBeGreaterThan(0);
    
    // Reload the page
    await page.reload();
    
    // Open Load Workflow modal
    await page.getByText('📂 Load Workflow').click();
    
    // Fill in workflow ID and load
    await page.getByTestId('workflow-id-input').fill(workflowId);
    await page.getByTestId('load-workflow-btn').click();
    
    // Verify workflow state is loaded
    await expect(page.getByTestId('workflow-id')).toContainText(workflowId, { timeout: 10000 });
    await expect(page.getByTestId('workflow-status')).toHaveText(/COMPLETED|FAILED/, { timeout: 10000 });
    
    // Verify events are replayed (should have similar count)
    await expect(page.getByTestId('event-entry').first()).toBeVisible({ timeout: 10000 });
    const eventCountAfter = await page.getByTestId('event-entry').count();
    expect(eventCountAfter).toBeGreaterThan(0);
    // Should have at least most of the events (allow for slight timing differences)
    expect(eventCountAfter).toBeGreaterThanOrEqual(eventCountBefore - 2);
  });

  test('should handle retry for retryable failed workflow', async ({ page }) => {
    await page.goto('/');
    
    // Expand config panel
    await page.getByText('⚙️ Config').click();
    
    // Create a workflow configured to fail with retryable error
    await page.getByTestId('config-input').fill(JSON.stringify({
      simulate_failure: "transient_once",
      prompt: "Test retry"
    }, null, 2));
    
    await page.getByTestId('submit-workflow-btn').click();
    
    // Wait for workflow to fail
    await expect(page.getByTestId('workflow-status')).toHaveText('FAILED', { timeout: 30000 });
    
    // Verify error is retryable
    await expect(page.getByTestId('workflow-error')).toBeVisible();
    await expect(page.getByTestId('error-retryable')).toContainText('true');
    
    // Verify retry button is enabled
    await expect(page.getByTestId('retry-btn')).toBeEnabled();
    
    // Click retry
    await page.getByTestId('retry-btn').click();
    
    // Verify workflow status transitions (should go back to processing)
    await expect(page.getByTestId('workflow-status')).not.toHaveText('FAILED', { timeout: 10000 });
    
    // Wait for workflow to complete (retry should succeed)
    await expect(page.getByTestId('workflow-status')).toHaveText(/COMPLETED|PROCESSING/, { timeout: 30000 });
  });

  test('should handle cancel for running workflow', async ({ page }) => {
    await page.goto('/');
    
    // Create a workflow
    await page.getByTestId('prompt-input').fill('Test cancel workflow');
    await page.getByTestId('submit-workflow-btn').click();
    
    // Wait for workflow to start processing
    await expect(page.getByTestId('workflow-status')).toBeVisible({ timeout: 10000 });
    
    // Verify cancel button is enabled (workflow not terminal yet)
    const initialStatus = await page.getByTestId('workflow-status').textContent();
    
    // If workflow is not terminal, cancel it
    if (!['COMPLETED', 'FAILED'].includes(initialStatus)) {
      await expect(page.getByTestId('cancel-btn')).toBeEnabled();
      await page.getByTestId('cancel-btn').click();
      
      // Wait for workflow to transition to FAILED
      await expect(page.getByTestId('workflow-status')).toHaveText('FAILED', { timeout: 15000 });
      
      // Verify error type is USER (cancelled)
      await expect(page.getByTestId('workflow-error')).toBeVisible();
      await expect(page.getByTestId('workflow-error')).toContainText('USER');
      await expect(page.getByTestId('error-retryable')).toContainText('false');
    }
    
    // Verify cancel button is now disabled (terminal state)
    await expect(page.getByTestId('cancel-btn')).toBeDisabled();
  });

  test('should show retry button only for retryable failures', async ({ page }) => {
    await page.goto('/');
    
    // Expand config panel
    await page.getByText('⚙️ Config').click();
    
    // Create a workflow configured to fail with permanent error
    await page.getByTestId('config-input').fill(JSON.stringify({
      simulate_failure: "permanent_once",
      prompt: "Test permanent failure"
    }, null, 2));
    
    await page.getByTestId('submit-workflow-btn').click();
    
    // Wait for workflow to fail
    await expect(page.getByTestId('workflow-status')).toHaveText('FAILED', { timeout: 30000 });
    
    // Verify error is not retryable
    await expect(page.getByTestId('workflow-error')).toBeVisible();
    await expect(page.getByTestId('error-retryable')).toContainText('false');
    
    // Verify retry button is disabled
    await expect(page.getByTestId('retry-btn')).toBeDisabled();
  });

  test('should display and update progress bar', async ({ page }) => {
    await page.goto('/');
    
    await page.getByTestId('prompt-input').fill('Test progress bar');
    await page.getByTestId('submit-workflow-btn').click();
    
    // Wait for workflow to start
    await expect(page.getByTestId('workflow-status')).toBeVisible({ timeout: 10000 });
    
    // Verify progress bar exists
    await expect(page.getByTestId('progress-bar')).toBeVisible();
    
    // Get initial progress
    const initialWidth = await page.getByTestId('progress-bar').evaluate((el) => el.style.width);
    
    // Wait a bit for progress to update
    await page.waitForTimeout(2000);
    
    // Get updated progress
    const updatedWidth = await page.getByTestId('progress-bar').evaluate((el) => el.style.width);
    
    // Progress should increase (or reach 100% if completed)
    const initial = parseInt(initialWidth) || 0;
    const updated = parseInt(updatedWidth) || 0;
    expect(updated).toBeGreaterThanOrEqual(initial);
  });

  test('should handle multiple workflows independently', async ({ page }) => {
    await page.goto('/');
    
    // Create first workflow
    await page.getByTestId('prompt-input').fill('First workflow');
    await page.getByTestId('submit-workflow-btn').click();
    await expect(page.getByTestId('workflow-id')).toBeVisible({ timeout: 10000 });
    const workflowId1 = await page.getByTestId('workflow-id').textContent();
    
    // Wait for first to reach terminal
    await expect(page.getByTestId('workflow-status')).toHaveText(/COMPLETED|FAILED/, { timeout: 30000 });
    
    // Reload page
    await page.reload();
    
    // Create second workflow
    await page.getByTestId('prompt-input').fill('Second workflow');
    await page.getByTestId('submit-workflow-btn').click();
    await expect(page.getByTestId('workflow-id')).toBeVisible({ timeout: 10000 });
    const workflowId2 = await page.getByTestId('workflow-id').textContent();
    
    // Verify different IDs
    expect(workflowId1).not.toBe(workflowId2);
    
    // Open Load Workflow modal and load first workflow again
    await page.getByText('📂 Load Workflow').click();
    await page.getByTestId('workflow-id-input').fill(workflowId1);
    await page.getByTestId('load-workflow-btn').click();
    
    // Verify first workflow state is loaded
    await expect(page.getByTestId('workflow-id')).toContainText(workflowId1, { timeout: 10000 });
  });
});
