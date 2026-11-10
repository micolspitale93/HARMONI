// End-to-end test of HARMONI Studio in a real browser (Playwright + Chromium).
// Run it with ./run_studio_e2e.sh (it creates a throwaway workspace and starts Studio):
// compose with live validation, save a tree, run the group interaction in simulation, add a service,
// create a module, run its tests, share it, and refuse to share a module whose checks fail.
const { chromium } = require('playwright');
const SHOTS = process.argv[2] || '.';
const URL = process.env.STUDIO_URL || 'http://localhost:8800';
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  page.on('dialog', async (d) => {
    const answers = { 'File name of the new tree': 'e2e_tree.json', 'Where?': 'core', 'File name of the configuration': 'e2e.yaml' };
    const key = Object.keys(answers).find((k) => d.message().startsWith(k));
    await (key ? d.accept(answers[key]) : d.accept());
  });
  const step = (s) => console.log('STEP', s);

  await page.goto(`${URL}/#compose`);
  await page.waitForSelector('.node-row');
  step('compose: group interaction opened');
  await page.screenshot({ path: `${SHOTS}/1-compose.png` });

  // select the "Ask orchestrator" node and edit a parameter
  await page.click('.node-row:has-text("Ask orchestrator")');
  await page.waitForSelector('#compose-props label.field');
  const timeout = page.locator('#compose-props label.field:has-text("timeout_s") input');
  await timeout.fill('not a number');
  await page.waitForSelector('.issue.error', { timeout: 5000 });
  step('validation shows the wrong type: ' + (await page.locator('.issue.error').first().innerText()).replace(/\s+/g, ' '));
  await timeout.fill('${llm_timeout_s}');
  await page.waitForSelector('#compose-toolbar .pill.ok', { timeout: 5000 });
  step('valid again');

  // new tree: add nodes from the palette by click
  await page.click('#compose-trees button:has-text("New")');
  await page.waitForSelector('.node-row:has-text("Main")');
  await page.click('.palette-item:has-text("ServiceAction")');
  await page.locator('#compose-props label.field:has-text("service") input').first().fill('speaker_furhat');
  await page.locator('#compose-props label.field:has-text("action") select').first().selectOption('DO');
  await page.locator('#compose-props label.field:has-text("input_value") input').fill('Hello from HARMONI Studio');
  await page.click('.node-row:has-text("Main")');
  await page.click('.palette-item:has-text("Wait")');
  await page.locator('#compose-props label.field:has-text("seconds") input').fill('0.2');
  await page.waitForSelector('#compose-toolbar .pill.ok', { timeout: 5000 });
  await page.click('#compose-toolbar button.primary');
  await page.waitForSelector('.toast.ok');
  step('new tree saved');
  await page.click('.seg button:has-text("Diagram")');
  await page.waitForSelector('svg.diagram');
  await page.screenshot({ path: `${SHOTS}/2-new-tree-diagram.png` });
  await page.click('.seg button:has-text("Outline")');

  // run the group interaction in simulation
  await page.click('.tabs button[data-page=run]');
  await page.locator('#run-controls select').first().selectOption('group_interaction.json');
  await page.waitForTimeout(300);
  await page.locator('#run-controls .row:has(code:text-is("max_scenes")) input').fill('6');
  await page.locator('#run-controls label.field:has-text("Tick period") input').fill('0.05');
  await page.click('#run-controls button:has-text("Start")');
  await page.waitForSelector('#run-status .pill.run', { timeout: 20000 });
  await page.waitForSelector('#run-status .pill.ok:text("finished")', { timeout: 60000 });
  const bubbles = await page.locator('#run-transcript .bubble').count();
  step(`simulation finished, ${bubbles} transcript lines`);
  await page.screenshot({ path: `${SHOTS}/3-run.png` });

  // services: open the mock config and add a service
  await page.click('.tabs button[data-page=services]');
  await page.click('#services-list .list-item:has-text("group_interaction_mock.yaml")');
  await page.waitForSelector('#services-main textarea');
  await page.locator('#services-side select').first().selectOption('mock');
  await page.locator('#services-side label.field:has-text("Service id") input').fill('camera_default');
  await page.click('#services-side button:has-text("Insert")');
  await page.waitForFunction(() => document.querySelector('#services-main textarea').value.includes('camera_default:'));
  step('service inserted into the YAML');
  await page.screenshot({ path: `${SHOTS}/4-services.png` });

  // modules: create a private detector, run its tests, then try to share it
  await page.click('.tabs button[data-page=modules]');
  await page.click('#modules-list button:has-text("New module")');
  await page.locator('#page-modules label.field:has-text("Name") input').first().fill('raised_hand');
  await page.locator('#page-modules label.field:has-text("Description") textarea').fill('Detects a raised hand in the camera image');
  await page.locator('#page-modules label.field:has-text("Author") input').fill('HARMONI team');
  await page.click('#page-modules .field button:has-text("+ Add")');
  const prow = page.locator('#page-modules .param-row').last();
  await prow.locator('input').nth(0).fill('threshold');
  await prow.locator('select').selectOption('float');
  await prow.locator('input').nth(1).fill('0.5');
  await page.waitForFunction(() => document.getElementById('wizard-preview').textContent.includes('class RaisedHandBackend'));
  await page.screenshot({ path: `${SHOTS}/5-module-wizard.png` });
  await page.click('#page-modules button:has-text("Create module")');
  await page.waitForSelector('#modules-main .toolbar .title:text("raised_hand")');
  step('module created');
  await page.click('#page-modules .seg button:has-text("Tests")');
  await page.click('#page-modules button:has-text("Run the tests")');
  await page.waitForSelector('#modules-main .pill:text("passed")', { timeout: 120000 });
  step('module tests passed');
  await page.click('#page-modules button:has-text("Share with everyone")');
  await page.waitForSelector('#modules-list .list-item:has-text("raised_hand") >> xpath=..', { timeout: 120000 });
  await page.waitForFunction(() => [...document.querySelectorAll('#modules-main .pill')].some((p) => p.textContent === 'public'), null, { timeout: 120000 });
  step('module with complete metadata shared: now public');
  // a module without author cannot be shared
  await page.click('#modules-list button:has-text("New module")');
  await page.locator('#page-modules label.field:has-text("Name") input').first().fill('door_sensor');
  await page.click('#page-modules .kind-card:has-text("sensor")');
  await page.locator('#page-modules label.field:has-text("Description") textarea').fill('Tells whether the door is open');
  await page.locator('#page-modules input[name=share]').last().check();
  await page.click('#page-modules button:has-text("Create module")');
  await page.waitForSelector('#page-modules .check.ko', { timeout: 120000 });
  const failed = await page.locator('#page-modules .check.ko').allInnerTexts();
  step('door_sensor stays private, failed checks: ' + failed.map((t) => t.replace('✗', '').trim().split('\n')[0]).join(' | '));
  await page.screenshot({ path: `${SHOTS}/6-module-checks.png` });

  // the new backend is offered in the Services page
  await page.click('.tabs button[data-page=services]');
  const options = await page.locator('#services-side select').first().locator('option').allInnerTexts();
  step('module listed as backend: ' + options.some((o) => o.includes('raised_hand')));

  await browser.close();
  if (errors.length) { console.error('BROWSER ERRORS', JSON.stringify(errors)); process.exit(1); }
  console.log('STUDIO E2E PASSED');
})().catch((e) => { console.error('FAILED', e.message); process.exit(1); });
