// The hub's «Notifications» permission, as this module's screens meet it (whatsapp_inbox#294).
//
// Both doors this module reads Meta through — the attachments (`whatsappMedia`) and the templates
// (`whatsappTemplates`) — are gated by the `notify` capability, which the hub denies until the
// owner turns it on (ADR-0079). Denied, they answer the stable code `capability_denied` (ADR-0055).
// Painting that as «could not load» or «Meta did not answer» sends the owner to retry or to wait,
// and neither will ever work: the pattern every platform uses for a denied permission (iOS, Android,
// Shopify apps) is to say WHICH permission is missing and take you to the switch.

import { doorErrorCode } from './meta-door-refusal';

/** The Permissions tab of the hub Settings, by the deep link the shell keeps in the hash. */
export const NOTIFY_PERMISSION_PATH = '/settings#permissions';

/** The door refused because the module lacks the permission — and only then. */
export function isNotifyPermissionDenied(e: unknown): boolean {
  return doorErrorCode(e) === 'capability_denied';
}

/** Takes the owner to the switch, the same way every other link of this module leaves it. */
export function openNotifyPermission(): void {
  window.history.pushState({}, '', NOTIFY_PERMISSION_PATH);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
