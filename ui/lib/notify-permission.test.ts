// whatsapp_inbox#294 — the attachments door and the templates door both answer `capability_denied`
// when the owner has not granted this module the hub's «Notifications» permission (`notify`,
// default-deny, ADR-0079). The screens have to tell THAT apart from a real failure, and send
// whoever can grant it to the hub's own switch.
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  NOTIFY_PERMISSION_PATH,
  isNotifyPermissionDenied,
  openNotifyPermission,
} from './notify-permission';

const refusal = (code: string) => Object.assign(new Error('whatever the door said'), { code });

describe('isNotifyPermissionDenied', () => {
  it('is the door refusing for want of the permission', () => {
    expect(isNotifyPermissionDenied(refusal('capability_denied'))).toBe(true);
  });

  it('is NOT any other refusal, nor a failure without a code', () => {
    for (const e of [refusal('cloud_unreachable'), refusal('permission_denied'), new Error('502'), null, undefined, 'x']) {
      expect(isNotifyPermissionDenied(e), String(e)).toBe(false);
    }
  });
});

describe('openNotifyPermission', () => {
  afterEach(() => vi.restoreAllMocks());

  it('is the Permissions tab of the hub Settings, by its deep link', () => {
    expect(NOTIFY_PERMISSION_PATH).toBe('/settings#permissions');
  });

  it('navigates the shell there (pushState + popstate, as every other link of this module)', () => {
    const push = vi.spyOn(window.history, 'pushState');
    const pops: Event[] = [];
    const listener = (e: Event) => pops.push(e);
    window.addEventListener('popstate', listener);
    openNotifyPermission();
    window.removeEventListener('popstate', listener);
    expect(push).toHaveBeenCalledWith({}, '', '/settings#permissions');
    expect(pops, 'the shell router is never told the address changed').toHaveLength(1);
  });
});
