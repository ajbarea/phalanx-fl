/**
 * Assistant branding configuration.
 * Update ASSISTANT_NAME to rebrand the assistant across the UI.
 */
const ASSISTANT_NAME = 'Argus';
const ASK_LABEL = `Ask ${ASSISTANT_NAME}`;

export const ASSISTANT_BRANDING = {
  name: ASSISTANT_NAME,
  askLabel: ASK_LABEL,
  navLabel: ASK_LABEL,
  pageTitle: ASK_LABEL,
  pageSubtitle: 'Ask questions about your federated learning experiments',
  panelTitle: ASSISTANT_NAME,
  assistantLabel: `${ASSISTANT_NAME} Assistant`,
  openButtonTitle: `Open ${ASSISTANT_NAME}`,
  openButtonAriaLabel: `Open ${ASSISTANT_NAME}`,
  panelAriaLabel: `${ASSISTANT_NAME} Assistant`,
  placeholder: `${ASK_LABEL}...`,
};
