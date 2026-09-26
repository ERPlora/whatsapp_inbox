var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __decorateClass = (decorators, target, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc(target, key) : target;
  for (var i7 = decorators.length - 1, decorator; i7 >= 0; i7--)
    if (decorator = decorators[i7])
      result = (kind ? decorator(target, key, result) : decorator(result)) || result;
  if (kind && result) __defProp(target, key, result);
  return result;
};

// @lit-labs/ssr-dom-shim/lib/element-internals.js
var ElementInternalsShim = class ElementInternals {
  get shadowRoot() {
    return this.__host.__shadowRoot;
  }
  constructor(_host) {
    this.ariaActiveDescendantElement = null;
    this.ariaAtomic = "";
    this.ariaAutoComplete = "";
    this.ariaBrailleLabel = "";
    this.ariaBrailleRoleDescription = "";
    this.ariaBusy = "";
    this.ariaChecked = "";
    this.ariaColCount = "";
    this.ariaColIndex = "";
    this.ariaColIndexText = "";
    this.ariaColSpan = "";
    this.ariaControlsElements = null;
    this.ariaCurrent = "";
    this.ariaDescribedByElements = null;
    this.ariaDescription = "";
    this.ariaDetailsElements = null;
    this.ariaDisabled = "";
    this.ariaErrorMessageElements = null;
    this.ariaExpanded = "";
    this.ariaFlowToElements = null;
    this.ariaHasPopup = "";
    this.ariaHidden = "";
    this.ariaInvalid = "";
    this.ariaKeyShortcuts = "";
    this.ariaLabel = "";
    this.ariaLabelledByElements = null;
    this.ariaLevel = "";
    this.ariaLive = "";
    this.ariaModal = "";
    this.ariaMultiLine = "";
    this.ariaMultiSelectable = "";
    this.ariaOrientation = "";
    this.ariaOwnsElements = null;
    this.ariaPlaceholder = "";
    this.ariaPosInSet = "";
    this.ariaPressed = "";
    this.ariaReadOnly = "";
    this.ariaRelevant = "";
    this.ariaRequired = "";
    this.ariaRoleDescription = "";
    this.ariaRowCount = "";
    this.ariaRowIndex = "";
    this.ariaRowIndexText = "";
    this.ariaRowSpan = "";
    this.ariaSelected = "";
    this.ariaSetSize = "";
    this.ariaSort = "";
    this.ariaValueMax = "";
    this.ariaValueMin = "";
    this.ariaValueNow = "";
    this.ariaValueText = "";
    this.role = "";
    this.form = null;
    this.labels = [];
    this.states = /* @__PURE__ */ new Set();
    this.validationMessage = "";
    this.validity = {};
    this.willValidate = true;
    this.__host = _host;
  }
  checkValidity() {
    console.warn("`ElementInternals.checkValidity()` was called on the server.This method always returns true.");
    return true;
  }
  reportValidity() {
    return true;
  }
  setFormValue() {
  }
  setValidity() {
  }
};

// @lit-labs/ssr-dom-shim/lib/events.js
var __classPrivateFieldSet = function(receiver, state, value, kind, f3) {
  if (kind === "m") throw new TypeError("Private method is not writable");
  if (kind === "a" && !f3) throw new TypeError("Private accessor was defined without a setter");
  if (typeof state === "function" ? receiver !== state || !f3 : !state.has(receiver)) throw new TypeError("Cannot write private member to an object whose class did not declare it");
  return kind === "a" ? f3.call(receiver, value) : f3 ? f3.value = value : state.set(receiver, value), value;
};
var __classPrivateFieldGet = function(receiver, state, kind, f3) {
  if (kind === "a" && !f3) throw new TypeError("Private accessor was defined without a getter");
  if (typeof state === "function" ? receiver !== state || !f3 : !state.has(receiver)) throw new TypeError("Cannot read private member from an object whose class did not declare it");
  return kind === "m" ? f3 : kind === "a" ? f3.call(receiver) : f3 ? f3.value : state.get(receiver);
};
var _Event_cancelable;
var _Event_bubbles;
var _Event_composed;
var _Event_defaultPrevented;
var _Event_timestamp;
var _Event_propagationStopped;
var _Event_type;
var _Event_target;
var _Event_isBeingDispatched;
var _a;
var _CustomEvent_detail;
var _b;
var NONE = 0;
var CAPTURING_PHASE = 1;
var AT_TARGET = 2;
var BUBBLING_PHASE = 3;
var enumerableProperty = { __proto__: null };
enumerableProperty.enumerable = true;
Object.freeze(enumerableProperty);
var EventShim = (_a = class Event {
  constructor(type, options = {}) {
    _Event_cancelable.set(this, false);
    _Event_bubbles.set(this, false);
    _Event_composed.set(this, false);
    _Event_defaultPrevented.set(this, false);
    _Event_timestamp.set(this, Date.now());
    _Event_propagationStopped.set(this, false);
    _Event_type.set(this, void 0);
    _Event_target.set(this, void 0);
    _Event_isBeingDispatched.set(this, void 0);
    this.NONE = NONE;
    this.CAPTURING_PHASE = CAPTURING_PHASE;
    this.AT_TARGET = AT_TARGET;
    this.BUBBLING_PHASE = BUBBLING_PHASE;
    if (arguments.length === 0)
      throw new Error(`The type argument must be specified`);
    if (typeof options !== "object" || !options) {
      throw new Error(`The "options" argument must be an object`);
    }
    const { bubbles, cancelable, composed } = options;
    __classPrivateFieldSet(this, _Event_cancelable, !!cancelable, "f");
    __classPrivateFieldSet(this, _Event_bubbles, !!bubbles, "f");
    __classPrivateFieldSet(this, _Event_composed, !!composed, "f");
    __classPrivateFieldSet(this, _Event_type, `${type}`, "f");
    __classPrivateFieldSet(this, _Event_target, null, "f");
    __classPrivateFieldSet(this, _Event_isBeingDispatched, false, "f");
  }
  initEvent(_type, _bubbles, _cancelable) {
    throw new Error("Method not implemented.");
  }
  stopImmediatePropagation() {
    this.stopPropagation();
  }
  preventDefault() {
    __classPrivateFieldSet(this, _Event_defaultPrevented, true, "f");
  }
  get target() {
    return __classPrivateFieldGet(this, _Event_target, "f");
  }
  get currentTarget() {
    return __classPrivateFieldGet(this, _Event_target, "f");
  }
  get srcElement() {
    return __classPrivateFieldGet(this, _Event_target, "f");
  }
  get type() {
    return __classPrivateFieldGet(this, _Event_type, "f");
  }
  get cancelable() {
    return __classPrivateFieldGet(this, _Event_cancelable, "f");
  }
  get defaultPrevented() {
    return __classPrivateFieldGet(this, _Event_cancelable, "f") && __classPrivateFieldGet(this, _Event_defaultPrevented, "f");
  }
  get timeStamp() {
    return __classPrivateFieldGet(this, _Event_timestamp, "f");
  }
  composedPath() {
    return __classPrivateFieldGet(this, _Event_isBeingDispatched, "f") ? [__classPrivateFieldGet(this, _Event_target, "f")] : [];
  }
  get returnValue() {
    return !__classPrivateFieldGet(this, _Event_cancelable, "f") || !__classPrivateFieldGet(this, _Event_defaultPrevented, "f");
  }
  get bubbles() {
    return __classPrivateFieldGet(this, _Event_bubbles, "f");
  }
  get composed() {
    return __classPrivateFieldGet(this, _Event_composed, "f");
  }
  get eventPhase() {
    return __classPrivateFieldGet(this, _Event_isBeingDispatched, "f") ? _a.AT_TARGET : _a.NONE;
  }
  get cancelBubble() {
    return __classPrivateFieldGet(this, _Event_propagationStopped, "f");
  }
  set cancelBubble(value) {
    if (value) {
      __classPrivateFieldSet(this, _Event_propagationStopped, true, "f");
    }
  }
  stopPropagation() {
    __classPrivateFieldSet(this, _Event_propagationStopped, true, "f");
  }
  get isTrusted() {
    return false;
  }
}, _Event_cancelable = /* @__PURE__ */ new WeakMap(), _Event_bubbles = /* @__PURE__ */ new WeakMap(), _Event_composed = /* @__PURE__ */ new WeakMap(), _Event_defaultPrevented = /* @__PURE__ */ new WeakMap(), _Event_timestamp = /* @__PURE__ */ new WeakMap(), _Event_propagationStopped = /* @__PURE__ */ new WeakMap(), _Event_type = /* @__PURE__ */ new WeakMap(), _Event_target = /* @__PURE__ */ new WeakMap(), _Event_isBeingDispatched = /* @__PURE__ */ new WeakMap(), _a.NONE = NONE, _a.CAPTURING_PHASE = CAPTURING_PHASE, _a.AT_TARGET = AT_TARGET, _a.BUBBLING_PHASE = BUBBLING_PHASE, _a);
Object.defineProperties(EventShim.prototype, {
  initEvent: enumerableProperty,
  stopImmediatePropagation: enumerableProperty,
  preventDefault: enumerableProperty,
  target: enumerableProperty,
  currentTarget: enumerableProperty,
  srcElement: enumerableProperty,
  type: enumerableProperty,
  cancelable: enumerableProperty,
  defaultPrevented: enumerableProperty,
  timeStamp: enumerableProperty,
  composedPath: enumerableProperty,
  returnValue: enumerableProperty,
  bubbles: enumerableProperty,
  composed: enumerableProperty,
  eventPhase: enumerableProperty,
  cancelBubble: enumerableProperty,
  stopPropagation: enumerableProperty,
  isTrusted: enumerableProperty
});
var CustomEventShim = (_b = class CustomEvent2 extends EventShim {
  constructor(type, options = {}) {
    super(type, options);
    _CustomEvent_detail.set(this, void 0);
    __classPrivateFieldSet(this, _CustomEvent_detail, options?.detail ?? null, "f");
  }
  initCustomEvent(_type, _bubbles, _cancelable, _detail) {
    throw new Error("Method not implemented.");
  }
  get detail() {
    return __classPrivateFieldGet(this, _CustomEvent_detail, "f");
  }
}, _CustomEvent_detail = /* @__PURE__ */ new WeakMap(), _b);
Object.defineProperties(CustomEventShim.prototype, {
  detail: enumerableProperty
});
var EventShimWithRealType = EventShim;
var CustomEventShimWithRealType = CustomEventShim;

// @lit-labs/ssr-dom-shim/lib/css.js
var _a2;
var CSSRuleShim = (_a2 = class CSSRule {
  constructor() {
    this.STYLE_RULE = 1;
    this.CHARSET_RULE = 2;
    this.IMPORT_RULE = 3;
    this.MEDIA_RULE = 4;
    this.FONT_FACE_RULE = 5;
    this.PAGE_RULE = 6;
    this.NAMESPACE_RULE = 10;
    this.KEYFRAMES_RULE = 7;
    this.KEYFRAME_RULE = 8;
    this.SUPPORTS_RULE = 12;
    this.COUNTER_STYLE_RULE = 11;
    this.FONT_FEATURE_VALUES_RULE = 14;
    this.MARGIN_RULE = 9;
    this.__parentStyleSheet = null;
    this.cssText = "";
  }
  get parentRule() {
    return null;
  }
  get parentStyleSheet() {
    return this.__parentStyleSheet;
  }
  get type() {
    return 0;
  }
}, _a2.STYLE_RULE = 1, _a2.CHARSET_RULE = 2, _a2.IMPORT_RULE = 3, _a2.MEDIA_RULE = 4, _a2.FONT_FACE_RULE = 5, _a2.PAGE_RULE = 6, _a2.NAMESPACE_RULE = 10, _a2.KEYFRAMES_RULE = 7, _a2.KEYFRAME_RULE = 8, _a2.SUPPORTS_RULE = 12, _a2.COUNTER_STYLE_RULE = 11, _a2.FONT_FEATURE_VALUES_RULE = 14, _a2.MARGIN_RULE = 9, _a2);

// @lit-labs/ssr-dom-shim/index.js
globalThis.Event ??= EventShimWithRealType;
globalThis.CustomEvent ??= CustomEventShimWithRealType;
var constructionToken = Symbol();
var isCaptureEventListener = (options) => typeof options === "boolean" ? options : options?.capture ?? false;
var enumerableProperty2 = { __proto__: null };
enumerableProperty2.enumerable = true;
Object.freeze(enumerableProperty2);
var EventTarget = class {
  constructor() {
    this.__eventListeners = /* @__PURE__ */ new Map();
    this.__captureEventListeners = /* @__PURE__ */ new Map();
  }
  addEventListener(type, callback, options) {
    if (callback === void 0 || callback === null) {
      return;
    }
    const eventListenersMap = isCaptureEventListener(options) ? this.__captureEventListeners : this.__eventListeners;
    let eventListeners = eventListenersMap.get(type);
    if (eventListeners === void 0) {
      eventListeners = /* @__PURE__ */ new Map();
      eventListenersMap.set(type, eventListeners);
    } else if (eventListeners.has(callback)) {
      return;
    }
    const normalizedOptions = typeof options === "object" && options ? options : {};
    normalizedOptions.signal?.addEventListener("abort", () => this.removeEventListener(type, callback, options));
    eventListeners.set(callback, normalizedOptions ?? {});
  }
  removeEventListener(type, callback, options) {
    if (callback === void 0 || callback === null) {
      return;
    }
    const eventListenersMap = isCaptureEventListener(options) ? this.__captureEventListeners : this.__eventListeners;
    const eventListeners = eventListenersMap.get(type);
    if (eventListeners !== void 0) {
      eventListeners.delete(callback);
      if (!eventListeners.size) {
        eventListenersMap.delete(type);
      }
    }
  }
  dispatchEvent(event) {
    let composedPath = this.__resolveFullEventPath();
    if (!event.composed && this.__host) {
      composedPath = composedPath.slice(0, composedPath.indexOf(this.__host));
    }
    let stopPropagation = false;
    let stopImmediatePropagation = false;
    let eventPhase = EventShimWithRealType.NONE;
    let target = null;
    let tmpTarget = null;
    let currentTarget = null;
    const originalStopPropagation = event.stopPropagation;
    const originalStopImmediatePropagation = event.stopImmediatePropagation;
    Object.defineProperties(event, {
      target: {
        get() {
          return target ?? tmpTarget;
        },
        ...enumerableProperty2
      },
      srcElement: {
        get() {
          return event.target;
        },
        ...enumerableProperty2
      },
      currentTarget: {
        get() {
          return currentTarget;
        },
        ...enumerableProperty2
      },
      eventPhase: {
        get() {
          return eventPhase;
        },
        ...enumerableProperty2
      },
      composedPath: {
        value: () => composedPath,
        ...enumerableProperty2
      },
      stopPropagation: {
        value: () => {
          stopPropagation = true;
          originalStopPropagation.call(event);
        },
        ...enumerableProperty2
      },
      stopImmediatePropagation: {
        value: () => {
          stopImmediatePropagation = true;
          originalStopImmediatePropagation.call(event);
        },
        ...enumerableProperty2
      }
    });
    const invokeEventListener = (listener, options, eventListenerMap) => {
      if (typeof listener === "function") {
        listener(event);
      } else if (typeof listener?.handleEvent === "function") {
        listener.handleEvent(event);
      }
      if (options.once) {
        eventListenerMap.delete(listener);
      }
    };
    const finishDispatch = () => {
      currentTarget = null;
      eventPhase = EventShimWithRealType.NONE;
      return !event.defaultPrevented;
    };
    const captureEventPath = composedPath.slice().reverse();
    target = !this.__host || !event.composed ? this : null;
    const retarget = (eventTargets) => {
      tmpTarget = this;
      while (tmpTarget.__host && eventTargets.includes(tmpTarget.__host)) {
        tmpTarget = tmpTarget.__host;
      }
    };
    for (const eventTarget of captureEventPath) {
      if (!target && (!tmpTarget || tmpTarget === eventTarget.__host)) {
        retarget(captureEventPath.slice(captureEventPath.indexOf(eventTarget)));
      }
      currentTarget = eventTarget;
      eventPhase = eventTarget === event.target ? EventShimWithRealType.AT_TARGET : EventShimWithRealType.CAPTURING_PHASE;
      const captureEventListeners = eventTarget.__captureEventListeners.get(event.type);
      if (captureEventListeners) {
        for (const [listener, options] of captureEventListeners) {
          invokeEventListener(listener, options, captureEventListeners);
          if (stopImmediatePropagation) {
            return finishDispatch();
          }
        }
      }
      if (stopPropagation) {
        return finishDispatch();
      }
    }
    const bubbleEventPath = event.bubbles ? composedPath : [this];
    tmpTarget = null;
    for (const eventTarget of bubbleEventPath) {
      if (!target && (!tmpTarget || eventTarget === tmpTarget.__host)) {
        retarget(bubbleEventPath.slice(0, bubbleEventPath.indexOf(eventTarget) + 1));
      }
      currentTarget = eventTarget;
      eventPhase = eventTarget === event.target ? EventShimWithRealType.AT_TARGET : EventShimWithRealType.BUBBLING_PHASE;
      const eventListeners = eventTarget.__eventListeners.get(event.type);
      if (eventListeners) {
        for (const [listener, options] of eventListeners) {
          invokeEventListener(listener, options, eventListeners);
          if (stopImmediatePropagation) {
            return finishDispatch();
          }
        }
      }
      if (stopPropagation) {
        return finishDispatch();
      }
    }
    return finishDispatch();
  }
  __resolveFullEventPath() {
    if (this.__eventPathCache) {
      return this.__eventPathCache;
    } else if (!this.__eventTargetParent) {
      return this.__eventPathCache = [this, documentShim, windowShim];
    } else {
      return this.__eventPathCache = [
        this,
        ...this.__eventTargetParent.__resolveFullEventPath()
      ];
    }
  }
};
var attributes = /* @__PURE__ */ new WeakMap();
var attributesForElement = (element) => {
  let attrs = attributes.get(element);
  if (attrs === void 0) {
    attributes.set(element, attrs = /* @__PURE__ */ new Map());
  }
  return attrs;
};
var NodeShim = class Node2 extends EventTarget {
  getRootNode(options) {
    if (options?.composed) {
      return document2;
    }
    const host = this.__host;
    return host?.__shadowRoot ?? document2;
  }
};
var DocumentShim = class Document2 extends NodeShim {
  get adoptedStyleSheets() {
    return [];
  }
  createTreeWalker() {
    return {};
  }
  createTextNode() {
    return {};
  }
  createElement() {
    return {};
  }
};
var documentShim = new DocumentShim();
var document2 = documentShim;
var WindowShim = class Window extends NodeShim {
  constructor(token) {
    super();
    if (token !== constructionToken) {
      throw new TypeError("Illegal constructor");
    }
    Object.assign(this, globalThis, {
      CustomElementRegistry,
      customElements: customElements2,
      document: document2,
      Document: DocumentShim,
      Element: ElementShim,
      EventTarget,
      HTMLElement: HTMLElementShim,
      Node: NodeShim,
      ShadowRoot: ShadowRootShim,
      window: this,
      Window: WindowShim
    });
  }
};
var ElementShim = class Element extends NodeShim {
  constructor() {
    super(...arguments);
    this.__shadowRootMode = null;
    this.__shadowRoot = null;
    this.__internals = null;
  }
  get attributes() {
    return Array.from(attributesForElement(this)).map(([name, value]) => ({
      name,
      value
    }));
  }
  get shadowRoot() {
    if (this.__shadowRootMode === "closed") {
      return null;
    }
    return this.__shadowRoot;
  }
  get localName() {
    return this.constructor.__localName;
  }
  get tagName() {
    return this.localName?.toUpperCase();
  }
  setAttribute(name, value) {
    attributesForElement(this).set(name, String(value));
  }
  removeAttribute(name) {
    attributesForElement(this).delete(name);
  }
  toggleAttribute(name, force) {
    if (this.hasAttribute(name)) {
      if (force === void 0 || !force) {
        this.removeAttribute(name);
        return false;
      }
    } else {
      if (force === void 0 || force) {
        this.setAttribute(name, "");
        return true;
      } else {
        return false;
      }
    }
    return true;
  }
  hasAttribute(name) {
    return attributesForElement(this).has(name);
  }
  attachShadow(init) {
    this.__shadowRootMode = init.mode;
    const shadowRoot = new ShadowRootShim(constructionToken, init);
    shadowRoot.__eventTargetParent = this;
    shadowRoot.__host = this;
    return this.__shadowRoot = shadowRoot;
  }
  attachInternals() {
    if (this.__internals !== null) {
      throw new Error(`Failed to execute 'attachInternals' on 'HTMLElement': ElementInternals for the specified element was already attached.`);
    }
    const internals = new ElementInternalsShim(this);
    this.__internals = internals;
    return internals;
  }
  getAttribute(name) {
    const value = attributesForElement(this).get(name);
    return value ?? null;
  }
};
var HTMLElementShim = class HTMLElement extends ElementShim {
};
var HTMLElementShimWithRealType = HTMLElementShim;
var ShadowRootShim = class ShadowRoot extends NodeShim {
  get host() {
    return this.__host;
  }
  constructor(constructionToken2, init) {
    super();
    if (constructionToken2 !== constructionToken2) {
      throw new TypeError("Illegal constructor");
    }
    this.mode = init.mode;
  }
};
globalThis.litServerRoot ??= Object.defineProperty(new HTMLElementShimWithRealType(), "localName", {
  // Patch localName (and tagName) to return a unique name.
  get() {
    return "lit-server-root";
  }
});
function promiseWithResolvers() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}
var CustomElementRegistry = class {
  constructor() {
    this.__definitions = /* @__PURE__ */ new Map();
    this.__reverseDefinitions = /* @__PURE__ */ new Map();
    this.__pendingWhenDefineds = /* @__PURE__ */ new Map();
  }
  define(name, ctor) {
    if (this.__definitions.has(name)) {
      if (true) {
        console.warn(`'CustomElementRegistry' already has "${name}" defined. This may have been caused by live reload or hot module replacement in which case it can be safely ignored.
Make sure to test your application with a production build as repeat registrations will throw in production.`);
      } else {
        throw new Error(`Failed to execute 'define' on 'CustomElementRegistry': the name "${name}" has already been used with this registry`);
      }
    }
    if (this.__reverseDefinitions.has(ctor)) {
      throw new Error(`Failed to execute 'define' on 'CustomElementRegistry': the constructor has already been used with this registry for the tag name ${this.__reverseDefinitions.get(ctor)}`);
    }
    ctor.__localName = name;
    this.__definitions.set(name, {
      ctor,
      // Note it's important we read `observedAttributes` in case it is a getter
      // with side-effects, as is the case in Lit, where it triggers class
      // finalization.
      //
      // TODO(aomarks) To be spec compliant, we should also capture the
      // registration-time lifecycle methods like `connectedCallback`. For them
      // to be actually accessible to e.g. the Lit SSR element renderer, though,
      // we'd need to introduce a new API for accessing them (since `get` only
      // returns the constructor).
      observedAttributes: ctor.observedAttributes ?? []
    });
    this.__reverseDefinitions.set(ctor, name);
    this.__pendingWhenDefineds.get(name)?.resolve(ctor);
    this.__pendingWhenDefineds.delete(name);
  }
  get(name) {
    const definition = this.__definitions.get(name);
    return definition?.ctor;
  }
  getName(ctor) {
    return this.__reverseDefinitions.get(ctor) ?? null;
  }
  initialize(_root) {
    throw new Error(`customElements.initialize is not currently supported in SSR. Please file a bug if you need it.`);
  }
  upgrade(_element) {
    throw new Error(`customElements.upgrade is not currently supported in SSR. Please file a bug if you need it.`);
  }
  async whenDefined(name) {
    const definition = this.__definitions.get(name);
    if (definition) {
      return definition.ctor;
    }
    let withResolvers = this.__pendingWhenDefineds.get(name);
    if (!withResolvers) {
      withResolvers = promiseWithResolvers();
      this.__pendingWhenDefineds.set(name, withResolvers);
    }
    return withResolvers.promise;
  }
};
var CustomElementRegistryShimWithRealType = CustomElementRegistry;
var customElements2 = new CustomElementRegistryShimWithRealType();
var windowShim = new WindowShim(constructionToken);

// @lit/reactive-element/node/css-tag.js
var t = globalThis;
var e = t.ShadowRoot && (void 0 === t.ShadyCSS || t.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype;
var s = Symbol();
var o = /* @__PURE__ */ new WeakMap();
var n = class {
  constructor(t5, e5, o7) {
    if (this._$cssResult$ = true, o7 !== s) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = t5, this.t = e5;
  }
  get styleSheet() {
    let t5 = this.o;
    const s5 = this.t;
    if (e && void 0 === t5) {
      const e5 = void 0 !== s5 && 1 === s5.length;
      e5 && (t5 = o.get(s5)), void 0 === t5 && ((this.o = t5 = new CSSStyleSheet()).replaceSync(this.cssText), e5 && o.set(s5, t5));
    }
    return t5;
  }
  toString() {
    return this.cssText;
  }
};
var r = (t5) => new n("string" == typeof t5 ? t5 : t5 + "", void 0, s);
var i = (t5, ...e5) => {
  const o7 = 1 === t5.length ? t5[0] : e5.reduce((e6, s5, o8) => e6 + ((t6) => {
    if (true === t6._$cssResult$) return t6.cssText;
    if ("number" == typeof t6) return t6;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + t6 + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(s5) + t5[o8 + 1], t5[0]);
  return new n(o7, t5, s);
};
var S = (s5, o7) => {
  if (e) s5.adoptedStyleSheets = o7.map((t5) => t5 instanceof CSSStyleSheet ? t5 : t5.styleSheet);
  else for (const e5 of o7) {
    const o8 = document.createElement("style"), n6 = t.litNonce;
    void 0 !== n6 && o8.setAttribute("nonce", n6), o8.textContent = e5.cssText, s5.appendChild(o8);
  }
};
var c = e || void 0 === t.CSSStyleSheet ? (t5) => t5 : (t5) => t5 instanceof CSSStyleSheet ? ((t6) => {
  let e5 = "";
  for (const s5 of t6.cssRules) e5 += s5.cssText;
  return r(e5);
})(t5) : t5;

// @lit/reactive-element/node/reactive-element.js
var { is: h, defineProperty: r2, getOwnPropertyDescriptor: o2, getOwnPropertyNames: n2, getOwnPropertySymbols: a, getPrototypeOf: c2 } = Object;
var l = globalThis;
l.customElements ??= customElements2;
var p = l.trustedTypes;
var d = p ? p.emptyScript : "";
var u = l.reactiveElementPolyfillSupport;
var f = (t5, s5) => t5;
var b = { toAttribute(t5, s5) {
  switch (s5) {
    case Boolean:
      t5 = t5 ? d : null;
      break;
    case Object:
    case Array:
      t5 = null == t5 ? t5 : JSON.stringify(t5);
  }
  return t5;
}, fromAttribute(t5, s5) {
  let i7 = t5;
  switch (s5) {
    case Boolean:
      i7 = null !== t5;
      break;
    case Number:
      i7 = null === t5 ? null : Number(t5);
      break;
    case Object:
    case Array:
      try {
        i7 = JSON.parse(t5);
      } catch (t6) {
        i7 = null;
      }
  }
  return i7;
} };
var m = (t5, s5) => !h(t5, s5);
var y = { attribute: true, type: String, converter: b, reflect: false, useDefault: false, hasChanged: m };
Symbol.metadata ??= Symbol("metadata"), l.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
var g = class extends (globalThis.HTMLElement ?? HTMLElementShimWithRealType) {
  static addInitializer(t5) {
    this._$Ei(), (this.l ??= []).push(t5);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(t5, s5 = y) {
    if (s5.state && (s5.attribute = false), this._$Ei(), this.prototype.hasOwnProperty(t5) && ((s5 = Object.create(s5)).wrapped = true), this.elementProperties.set(t5, s5), !s5.noAccessor) {
      const i7 = Symbol(), e5 = this.getPropertyDescriptor(t5, i7, s5);
      void 0 !== e5 && r2(this.prototype, t5, e5);
    }
  }
  static getPropertyDescriptor(t5, s5, i7) {
    const { get: e5, set: h4 } = o2(this.prototype, t5) ?? { get() {
      return this[s5];
    }, set(t6) {
      this[s5] = t6;
    } };
    return { get: e5, set(s6) {
      const r6 = e5?.call(this);
      h4?.call(this, s6), this.requestUpdate(t5, r6, i7);
    }, configurable: true, enumerable: true };
  }
  static getPropertyOptions(t5) {
    return this.elementProperties.get(t5) ?? y;
  }
  static _$Ei() {
    if (this.hasOwnProperty(f("elementProperties"))) return;
    const t5 = c2(this);
    t5.finalize(), void 0 !== t5.l && (this.l = [...t5.l]), this.elementProperties = new Map(t5.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(f("finalized"))) return;
    if (this.finalized = true, this._$Ei(), this.hasOwnProperty(f("properties"))) {
      const t6 = this.properties, s5 = [...n2(t6), ...a(t6)];
      for (const i7 of s5) this.createProperty(i7, t6[i7]);
    }
    const t5 = this[Symbol.metadata];
    if (null !== t5) {
      const s5 = litPropertyMetadata.get(t5);
      if (void 0 !== s5) for (const [t6, i7] of s5) this.elementProperties.set(t6, i7);
    }
    this._$Eh = /* @__PURE__ */ new Map();
    for (const [t6, s5] of this.elementProperties) {
      const i7 = this._$Eu(t6, s5);
      void 0 !== i7 && this._$Eh.set(i7, t6);
    }
    this.elementStyles = this.finalizeStyles(this.styles);
  }
  static finalizeStyles(t5) {
    const s5 = [];
    if (Array.isArray(t5)) {
      const e5 = new Set(t5.flat(1 / 0).reverse());
      for (const t6 of e5) s5.unshift(c(t6));
    } else void 0 !== t5 && s5.push(c(t5));
    return s5;
  }
  static _$Eu(t5, s5) {
    const i7 = s5.attribute;
    return false === i7 ? void 0 : "string" == typeof i7 ? i7 : "string" == typeof t5 ? t5.toLowerCase() : void 0;
  }
  constructor() {
    super(), this._$Ep = void 0, this.isUpdatePending = false, this.hasUpdated = false, this._$Em = null, this._$Ev();
  }
  _$Ev() {
    this._$ES = new Promise((t5) => this.enableUpdating = t5), this._$AL = /* @__PURE__ */ new Map(), this._$E_(), this.requestUpdate(), this.constructor.l?.forEach((t5) => t5(this));
  }
  addController(t5) {
    (this._$EO ??= /* @__PURE__ */ new Set()).add(t5), void 0 !== this.renderRoot && this.isConnected && t5.hostConnected?.();
  }
  removeController(t5) {
    this._$EO?.delete(t5);
  }
  _$E_() {
    const t5 = /* @__PURE__ */ new Map(), s5 = this.constructor.elementProperties;
    for (const i7 of s5.keys()) this.hasOwnProperty(i7) && (t5.set(i7, this[i7]), delete this[i7]);
    t5.size > 0 && (this._$Ep = t5);
  }
  createRenderRoot() {
    const t5 = this.shadowRoot ?? this.attachShadow(this.constructor.shadowRootOptions);
    return S(t5, this.constructor.elementStyles), t5;
  }
  connectedCallback() {
    this.renderRoot ??= this.createRenderRoot(), this.enableUpdating(true), this._$EO?.forEach((t5) => t5.hostConnected?.());
  }
  enableUpdating(t5) {
  }
  disconnectedCallback() {
    this._$EO?.forEach((t5) => t5.hostDisconnected?.());
  }
  attributeChangedCallback(t5, s5, i7) {
    this._$AK(t5, i7);
  }
  _$ET(t5, s5) {
    const i7 = this.constructor.elementProperties.get(t5), e5 = this.constructor._$Eu(t5, i7);
    if (void 0 !== e5 && true === i7.reflect) {
      const h4 = (void 0 !== i7.converter?.toAttribute ? i7.converter : b).toAttribute(s5, i7.type);
      this._$Em = t5, null == h4 ? this.removeAttribute(e5) : this.setAttribute(e5, h4), this._$Em = null;
    }
  }
  _$AK(t5, s5) {
    const i7 = this.constructor, e5 = i7._$Eh.get(t5);
    if (void 0 !== e5 && this._$Em !== e5) {
      const t6 = i7.getPropertyOptions(e5), h4 = "function" == typeof t6.converter ? { fromAttribute: t6.converter } : void 0 !== t6.converter?.fromAttribute ? t6.converter : b;
      this._$Em = e5;
      const r6 = h4.fromAttribute(s5, t6.type);
      this[e5] = r6 ?? this._$Ej?.get(e5) ?? r6, this._$Em = null;
    }
  }
  requestUpdate(t5, s5, i7, e5 = false, h4) {
    if (void 0 !== t5) {
      const r6 = this.constructor;
      if (false === e5 && (h4 = this[t5]), i7 ??= r6.getPropertyOptions(t5), !((i7.hasChanged ?? m)(h4, s5) || i7.useDefault && i7.reflect && h4 === this._$Ej?.get(t5) && !this.hasAttribute(r6._$Eu(t5, i7)))) return;
      this.C(t5, s5, i7);
    }
    false === this.isUpdatePending && (this._$ES = this._$EP());
  }
  C(t5, s5, { useDefault: i7, reflect: e5, wrapped: h4 }, r6) {
    i7 && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(t5) && (this._$Ej.set(t5, r6 ?? s5 ?? this[t5]), true !== h4 || void 0 !== r6) || (this._$AL.has(t5) || (this.hasUpdated || i7 || (s5 = void 0), this._$AL.set(t5, s5)), true === e5 && this._$Em !== t5 && (this._$Eq ??= /* @__PURE__ */ new Set()).add(t5));
  }
  async _$EP() {
    this.isUpdatePending = true;
    try {
      await this._$ES;
    } catch (t6) {
      Promise.reject(t6);
    }
    const t5 = this.scheduleUpdate();
    return null != t5 && await t5, !this.isUpdatePending;
  }
  scheduleUpdate() {
    return this.performUpdate();
  }
  performUpdate() {
    if (!this.isUpdatePending) return;
    if (!this.hasUpdated) {
      if (this.renderRoot ??= this.createRenderRoot(), this._$Ep) {
        for (const [t7, s6] of this._$Ep) this[t7] = s6;
        this._$Ep = void 0;
      }
      const t6 = this.constructor.elementProperties;
      if (t6.size > 0) for (const [s6, i7] of t6) {
        const { wrapped: t7 } = i7, e5 = this[s6];
        true !== t7 || this._$AL.has(s6) || void 0 === e5 || this.C(s6, void 0, i7, e5);
      }
    }
    let t5 = false;
    const s5 = this._$AL;
    try {
      t5 = this.shouldUpdate(s5), t5 ? (this.willUpdate(s5), this._$EO?.forEach((t6) => t6.hostUpdate?.()), this.update(s5)) : this._$EM();
    } catch (s6) {
      throw t5 = false, this._$EM(), s6;
    }
    t5 && this._$AE(s5);
  }
  willUpdate(t5) {
  }
  _$AE(t5) {
    this._$EO?.forEach((t6) => t6.hostUpdated?.()), this.hasUpdated || (this.hasUpdated = true, this.firstUpdated(t5)), this.updated(t5);
  }
  _$EM() {
    this._$AL = /* @__PURE__ */ new Map(), this.isUpdatePending = false;
  }
  get updateComplete() {
    return this.getUpdateComplete();
  }
  getUpdateComplete() {
    return this._$ES;
  }
  shouldUpdate(t5) {
    return true;
  }
  update(t5) {
    this._$Eq &&= this._$Eq.forEach((t6) => this._$ET(t6, this[t6])), this._$EM();
  }
  updated(t5) {
  }
  firstUpdated(t5) {
  }
};
g.elementStyles = [], g.shadowRootOptions = { mode: "open" }, g[f("elementProperties")] = /* @__PURE__ */ new Map(), g[f("finalized")] = /* @__PURE__ */ new Map(), u?.({ ReactiveElement: g }), (l.reactiveElementVersions ??= []).push("2.1.2");

// lit-html/lit-html.js
var t2 = globalThis;
var i2 = (t5) => t5;
var s2 = t2.trustedTypes;
var e2 = s2 ? s2.createPolicy("lit-html", { createHTML: (t5) => t5 }) : void 0;
var h2 = "$lit$";
var o3 = `lit$${Math.random().toFixed(9).slice(2)}$`;
var n3 = "?" + o3;
var r3 = `<${n3}>`;
var l2 = document;
var c3 = () => l2.createComment("");
var a2 = (t5) => null === t5 || "object" != typeof t5 && "function" != typeof t5;
var u2 = Array.isArray;
var d2 = (t5) => u2(t5) || "function" == typeof t5?.[Symbol.iterator];
var f2 = "[ 	\n\f\r]";
var v = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g;
var _ = /-->/g;
var m2 = />/g;
var p2 = RegExp(`>|${f2}(?:([^\\s"'>=/]+)(${f2}*=${f2}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`, "g");
var g2 = /'/g;
var $ = /"/g;
var y2 = /^(?:script|style|textarea|title)$/i;
var x = (t5) => (i7, ...s5) => ({ _$litType$: t5, strings: i7, values: s5 });
var b2 = x(1);
var w = x(2);
var T = x(3);
var E = Symbol.for("lit-noChange");
var A = Symbol.for("lit-nothing");
var C = /* @__PURE__ */ new WeakMap();
var P = l2.createTreeWalker(l2, 129);
function V(t5, i7) {
  if (!u2(t5) || !t5.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return void 0 !== e2 ? e2.createHTML(i7) : i7;
}
var N = (t5, i7) => {
  const s5 = t5.length - 1, e5 = [];
  let n6, l3 = 2 === i7 ? "<svg>" : 3 === i7 ? "<math>" : "", c5 = v;
  for (let i8 = 0; i8 < s5; i8++) {
    const s6 = t5[i8];
    let a3, u5, d3 = -1, f3 = 0;
    for (; f3 < s6.length && (c5.lastIndex = f3, u5 = c5.exec(s6), null !== u5); ) f3 = c5.lastIndex, c5 === v ? "!--" === u5[1] ? c5 = _ : void 0 !== u5[1] ? c5 = m2 : void 0 !== u5[2] ? (y2.test(u5[2]) && (n6 = RegExp("</" + u5[2], "g")), c5 = p2) : void 0 !== u5[3] && (c5 = p2) : c5 === p2 ? ">" === u5[0] ? (c5 = n6 ?? v, d3 = -1) : void 0 === u5[1] ? d3 = -2 : (d3 = c5.lastIndex - u5[2].length, a3 = u5[1], c5 = void 0 === u5[3] ? p2 : '"' === u5[3] ? $ : g2) : c5 === $ || c5 === g2 ? c5 = p2 : c5 === _ || c5 === m2 ? c5 = v : (c5 = p2, n6 = void 0);
    const x2 = c5 === p2 && t5[i8 + 1].startsWith("/>") ? " " : "";
    l3 += c5 === v ? s6 + r3 : d3 >= 0 ? (e5.push(a3), s6.slice(0, d3) + h2 + s6.slice(d3) + o3 + x2) : s6 + o3 + (-2 === d3 ? i8 : x2);
  }
  return [V(t5, l3 + (t5[s5] || "<?>") + (2 === i7 ? "</svg>" : 3 === i7 ? "</math>" : "")), e5];
};
var S2 = class _S {
  constructor({ strings: t5, _$litType$: i7 }, e5) {
    let r6;
    this.parts = [];
    let l3 = 0, a3 = 0;
    const u5 = t5.length - 1, d3 = this.parts, [f3, v3] = N(t5, i7);
    if (this.el = _S.createElement(f3, e5), P.currentNode = this.el.content, 2 === i7 || 3 === i7) {
      const t6 = this.el.content.firstChild;
      t6.replaceWith(...t6.childNodes);
    }
    for (; null !== (r6 = P.nextNode()) && d3.length < u5; ) {
      if (1 === r6.nodeType) {
        if (r6.hasAttributes()) for (const t6 of r6.getAttributeNames()) if (t6.endsWith(h2)) {
          const i8 = v3[a3++], s5 = r6.getAttribute(t6).split(o3), e6 = /([.?@])?(.*)/.exec(i8);
          d3.push({ type: 1, index: l3, name: e6[2], strings: s5, ctor: "." === e6[1] ? I : "?" === e6[1] ? L : "@" === e6[1] ? z : H }), r6.removeAttribute(t6);
        } else t6.startsWith(o3) && (d3.push({ type: 6, index: l3 }), r6.removeAttribute(t6));
        if (y2.test(r6.tagName)) {
          const t6 = r6.textContent.split(o3), i8 = t6.length - 1;
          if (i8 > 0) {
            r6.textContent = s2 ? s2.emptyScript : "";
            for (let s5 = 0; s5 < i8; s5++) r6.append(t6[s5], c3()), P.nextNode(), d3.push({ type: 2, index: ++l3 });
            r6.append(t6[i8], c3());
          }
        }
      } else if (8 === r6.nodeType) if (r6.data === n3) d3.push({ type: 2, index: l3 });
      else {
        let t6 = -1;
        for (; -1 !== (t6 = r6.data.indexOf(o3, t6 + 1)); ) d3.push({ type: 7, index: l3 }), t6 += o3.length - 1;
      }
      l3++;
    }
  }
  static createElement(t5, i7) {
    const s5 = l2.createElement("template");
    return s5.innerHTML = t5, s5;
  }
};
function M(t5, i7, s5 = t5, e5) {
  if (i7 === E) return i7;
  let h4 = void 0 !== e5 ? s5._$Co?.[e5] : s5._$Cl;
  const o7 = a2(i7) ? void 0 : i7._$litDirective$;
  return h4?.constructor !== o7 && (h4?._$AO?.(false), void 0 === o7 ? h4 = void 0 : (h4 = new o7(t5), h4._$AT(t5, s5, e5)), void 0 !== e5 ? (s5._$Co ??= [])[e5] = h4 : s5._$Cl = h4), void 0 !== h4 && (i7 = M(t5, h4._$AS(t5, i7.values), h4, e5)), i7;
}
var R = class {
  constructor(t5, i7) {
    this._$AV = [], this._$AN = void 0, this._$AD = t5, this._$AM = i7;
  }
  get parentNode() {
    return this._$AM.parentNode;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  u(t5) {
    const { el: { content: i7 }, parts: s5 } = this._$AD, e5 = (t5?.creationScope ?? l2).importNode(i7, true);
    P.currentNode = e5;
    let h4 = P.nextNode(), o7 = 0, n6 = 0, r6 = s5[0];
    for (; void 0 !== r6; ) {
      if (o7 === r6.index) {
        let i8;
        2 === r6.type ? i8 = new k(h4, h4.nextSibling, this, t5) : 1 === r6.type ? i8 = new r6.ctor(h4, r6.name, r6.strings, this, t5) : 6 === r6.type && (i8 = new Z(h4, this, t5)), this._$AV.push(i8), r6 = s5[++n6];
      }
      o7 !== r6?.index && (h4 = P.nextNode(), o7++);
    }
    return P.currentNode = l2, e5;
  }
  p(t5) {
    let i7 = 0;
    for (const s5 of this._$AV) void 0 !== s5 && (void 0 !== s5.strings ? (s5._$AI(t5, s5, i7), i7 += s5.strings.length - 2) : s5._$AI(t5[i7])), i7++;
  }
};
var k = class _k {
  get _$AU() {
    return this._$AM?._$AU ?? this._$Cv;
  }
  constructor(t5, i7, s5, e5) {
    this.type = 2, this._$AH = A, this._$AN = void 0, this._$AA = t5, this._$AB = i7, this._$AM = s5, this.options = e5, this._$Cv = e5?.isConnected ?? true;
  }
  get parentNode() {
    let t5 = this._$AA.parentNode;
    const i7 = this._$AM;
    return void 0 !== i7 && 11 === t5?.nodeType && (t5 = i7.parentNode), t5;
  }
  get startNode() {
    return this._$AA;
  }
  get endNode() {
    return this._$AB;
  }
  _$AI(t5, i7 = this) {
    t5 = M(this, t5, i7), a2(t5) ? t5 === A || null == t5 || "" === t5 ? (this._$AH !== A && this._$AR(), this._$AH = A) : t5 !== this._$AH && t5 !== E && this._(t5) : void 0 !== t5._$litType$ ? this.$(t5) : void 0 !== t5.nodeType ? this.T(t5) : d2(t5) ? this.k(t5) : this._(t5);
  }
  O(t5) {
    return this._$AA.parentNode.insertBefore(t5, this._$AB);
  }
  T(t5) {
    this._$AH !== t5 && (this._$AR(), this._$AH = this.O(t5));
  }
  _(t5) {
    this._$AH !== A && a2(this._$AH) ? this._$AA.nextSibling.data = t5 : this.T(l2.createTextNode(t5)), this._$AH = t5;
  }
  $(t5) {
    const { values: i7, _$litType$: s5 } = t5, e5 = "number" == typeof s5 ? this._$AC(t5) : (void 0 === s5.el && (s5.el = S2.createElement(V(s5.h, s5.h[0]), this.options)), s5);
    if (this._$AH?._$AD === e5) this._$AH.p(i7);
    else {
      const t6 = new R(e5, this), s6 = t6.u(this.options);
      t6.p(i7), this.T(s6), this._$AH = t6;
    }
  }
  _$AC(t5) {
    let i7 = C.get(t5.strings);
    return void 0 === i7 && C.set(t5.strings, i7 = new S2(t5)), i7;
  }
  k(t5) {
    u2(this._$AH) || (this._$AH = [], this._$AR());
    const i7 = this._$AH;
    let s5, e5 = 0;
    for (const h4 of t5) e5 === i7.length ? i7.push(s5 = new _k(this.O(c3()), this.O(c3()), this, this.options)) : s5 = i7[e5], s5._$AI(h4), e5++;
    e5 < i7.length && (this._$AR(s5 && s5._$AB.nextSibling, e5), i7.length = e5);
  }
  _$AR(t5 = this._$AA.nextSibling, s5) {
    for (this._$AP?.(false, true, s5); t5 !== this._$AB; ) {
      const s6 = i2(t5).nextSibling;
      i2(t5).remove(), t5 = s6;
    }
  }
  setConnected(t5) {
    void 0 === this._$AM && (this._$Cv = t5, this._$AP?.(t5));
  }
};
var H = class {
  get tagName() {
    return this.element.tagName;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  constructor(t5, i7, s5, e5, h4) {
    this.type = 1, this._$AH = A, this._$AN = void 0, this.element = t5, this.name = i7, this._$AM = e5, this.options = h4, s5.length > 2 || "" !== s5[0] || "" !== s5[1] ? (this._$AH = Array(s5.length - 1).fill(new String()), this.strings = s5) : this._$AH = A;
  }
  _$AI(t5, i7 = this, s5, e5) {
    const h4 = this.strings;
    let o7 = false;
    if (void 0 === h4) t5 = M(this, t5, i7, 0), o7 = !a2(t5) || t5 !== this._$AH && t5 !== E, o7 && (this._$AH = t5);
    else {
      const e6 = t5;
      let n6, r6;
      for (t5 = h4[0], n6 = 0; n6 < h4.length - 1; n6++) r6 = M(this, e6[s5 + n6], i7, n6), r6 === E && (r6 = this._$AH[n6]), o7 ||= !a2(r6) || r6 !== this._$AH[n6], r6 === A ? t5 = A : t5 !== A && (t5 += (r6 ?? "") + h4[n6 + 1]), this._$AH[n6] = r6;
    }
    o7 && !e5 && this.j(t5);
  }
  j(t5) {
    t5 === A ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, t5 ?? "");
  }
};
var I = class extends H {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(t5) {
    this.element[this.name] = t5 === A ? void 0 : t5;
  }
};
var L = class extends H {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(t5) {
    this.element.toggleAttribute(this.name, !!t5 && t5 !== A);
  }
};
var z = class extends H {
  constructor(t5, i7, s5, e5, h4) {
    super(t5, i7, s5, e5, h4), this.type = 5;
  }
  _$AI(t5, i7 = this) {
    if ((t5 = M(this, t5, i7, 0) ?? A) === E) return;
    const s5 = this._$AH, e5 = t5 === A && s5 !== A || t5.capture !== s5.capture || t5.once !== s5.once || t5.passive !== s5.passive, h4 = t5 !== A && (s5 === A || e5);
    e5 && this.element.removeEventListener(this.name, this, s5), h4 && this.element.addEventListener(this.name, this, t5), this._$AH = t5;
  }
  handleEvent(t5) {
    "function" == typeof this._$AH ? this._$AH.call(this.options?.host ?? this.element, t5) : this._$AH.handleEvent(t5);
  }
};
var Z = class {
  constructor(t5, i7, s5) {
    this.element = t5, this.type = 6, this._$AN = void 0, this._$AM = i7, this.options = s5;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AI(t5) {
    M(this, t5);
  }
};
var j = { M: h2, P: o3, A: n3, C: 1, L: N, R, D: d2, V: M, I: k, H, N: L, U: z, B: I, F: Z };
var B = t2.litHtmlPolyfillSupport;
B?.(S2, k), (t2.litHtmlVersions ??= []).push("3.3.3");
var D = (t5, i7, s5) => {
  const e5 = s5?.renderBefore ?? i7;
  let h4 = e5._$litPart$;
  if (void 0 === h4) {
    const t6 = s5?.renderBefore ?? null;
    e5._$litPart$ = h4 = new k(i7.insertBefore(c3(), t6), t6, void 0, s5 ?? {});
  }
  return h4._$AI(t5), h4;
};

// lit-element/lit-element.js
var s3 = globalThis;
var i3 = class extends g {
  constructor() {
    super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
  }
  createRenderRoot() {
    const t5 = super.createRenderRoot();
    return this.renderOptions.renderBefore ??= t5.firstChild, t5;
  }
  update(t5) {
    const r6 = this.render();
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(t5), this._$Do = D(r6, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    super.connectedCallback(), this._$Do?.setConnected(true);
  }
  disconnectedCallback() {
    super.disconnectedCallback(), this._$Do?.setConnected(false);
  }
  render() {
    return E;
  }
};
i3._$litElement$ = true, i3["finalized"] = true, s3.litElementHydrateSupport?.({ LitElement: i3 });
var o4 = s3.litElementPolyfillSupport;
o4?.({ LitElement: i3 });
(s3.litElementVersions ??= []).push("4.2.2");

// @lit/reactive-element/node/decorators/property.js
var o5 = { attribute: true, type: String, converter: b, reflect: false, hasChanged: m };
var r4 = (t5 = o5, e5, r6) => {
  const { kind: n6, metadata: i7 } = r6;
  let s5 = globalThis.litPropertyMetadata.get(i7);
  if (void 0 === s5 && globalThis.litPropertyMetadata.set(i7, s5 = /* @__PURE__ */ new Map()), "setter" === n6 && ((t5 = Object.create(t5)).wrapped = true), s5.set(r6.name, t5), "accessor" === n6) {
    const { name: o7 } = r6;
    return { set(r7) {
      const n7 = e5.get.call(this);
      e5.set.call(this, r7), this.requestUpdate(o7, n7, t5, true, r7);
    }, init(e6) {
      return void 0 !== e6 && this.C(o7, void 0, t5, e6), e6;
    } };
  }
  if ("setter" === n6) {
    const { name: o7 } = r6;
    return function(r7) {
      const n7 = this[o7];
      e5.call(this, r7), this.requestUpdate(o7, n7, t5, true, r7);
    };
  }
  throw Error("Unsupported decorator location: " + n6);
};
function n4(t5) {
  return (e5, o7) => "object" == typeof o7 ? r4(t5, e5, o7) : ((t6, e6, o8) => {
    const r6 = e6.hasOwnProperty(o8);
    return e6.constructor.createProperty(o8, t6), r6 ? Object.getOwnPropertyDescriptor(e6, o8) : void 0;
  })(t5, e5, o7);
}

// @lit/reactive-element/node/decorators/state.js
function r5(r6) {
  return n4({ ...r6, state: true, attribute: false });
}

// @erplora/outfitkit/dist/define.js
function define(tag, ctor) {
  if (typeof customElements !== "undefined" && !customElements.get(tag)) {
    customElements.define(tag, ctor);
  }
}

// lit-html/directive.js
var t3 = { ATTRIBUTE: 1, CHILD: 2, PROPERTY: 3, BOOLEAN_ATTRIBUTE: 4, EVENT: 5, ELEMENT: 6 };
var e4 = (t5) => (...e5) => ({ _$litDirective$: t5, values: e5 });
var i4 = class {
  constructor(t5) {
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AT(t5, e5, i7) {
    this._$Ct = t5, this._$AM = e5, this._$Ci = i7;
  }
  _$AS(t5, e5) {
    return this.update(t5, e5);
  }
  update(t5, e5) {
    return this.render(...e5);
  }
};

// lit-html/directive-helpers.js
var { I: t4 } = j;
var i5 = (o7) => o7;
var s4 = () => document.createComment("");
var v2 = (o7, n6, e5) => {
  const l3 = o7._$AA.parentNode, d3 = void 0 === n6 ? o7._$AB : n6._$AA;
  if (void 0 === e5) {
    const i7 = l3.insertBefore(s4(), d3), n7 = l3.insertBefore(s4(), d3);
    e5 = new t4(i7, n7, o7, o7.options);
  } else {
    const t5 = e5._$AB.nextSibling, n7 = e5._$AM, c5 = n7 !== o7;
    if (c5) {
      let t6;
      e5._$AQ?.(o7), e5._$AM = o7, void 0 !== e5._$AP && (t6 = o7._$AU) !== n7._$AU && e5._$AP(t6);
    }
    if (t5 !== d3 || c5) {
      let o8 = e5._$AA;
      for (; o8 !== t5; ) {
        const t6 = i5(o8).nextSibling;
        i5(l3).insertBefore(o8, d3), o8 = t6;
      }
    }
  }
  return e5;
};
var u3 = (o7, t5, i7 = o7) => (o7._$AI(t5, i7), o7);
var m3 = {};
var p3 = (o7, t5 = m3) => o7._$AH = t5;
var M2 = (o7) => o7._$AH;
var h3 = (o7) => {
  o7._$AR(), o7._$AA.remove();
};

// lit-html/directives/repeat.js
var u4 = (e5, s5, t5) => {
  const r6 = /* @__PURE__ */ new Map();
  for (let l3 = s5; l3 <= t5; l3++) r6.set(e5[l3], l3);
  return r6;
};
var c4 = e4(class extends i4 {
  constructor(e5) {
    if (super(e5), e5.type !== t3.CHILD) throw Error("repeat() can only be used in text expressions");
  }
  dt(e5, s5, t5) {
    let r6;
    void 0 === t5 ? t5 = s5 : void 0 !== s5 && (r6 = s5);
    const l3 = [], o7 = [];
    let i7 = 0;
    for (const s6 of e5) l3[i7] = r6 ? r6(s6, i7) : i7, o7[i7] = t5(s6, i7), i7++;
    return { values: o7, keys: l3 };
  }
  render(e5, s5, t5) {
    return this.dt(e5, s5, t5).values;
  }
  update(s5, [t5, r6, c5]) {
    const d3 = M2(s5), { values: p4, keys: a3 } = this.dt(t5, r6, c5);
    if (!Array.isArray(d3)) return this.ut = a3, p4;
    const h4 = this.ut ??= [], v3 = [];
    let m4, y3, x2 = 0, j2 = d3.length - 1, k2 = 0, w2 = p4.length - 1;
    for (; x2 <= j2 && k2 <= w2; ) if (null === d3[x2]) x2++;
    else if (null === d3[j2]) j2--;
    else if (h4[x2] === a3[k2]) v3[k2] = u3(d3[x2], p4[k2]), x2++, k2++;
    else if (h4[j2] === a3[w2]) v3[w2] = u3(d3[j2], p4[w2]), j2--, w2--;
    else if (h4[x2] === a3[w2]) v3[w2] = u3(d3[x2], p4[w2]), v2(s5, v3[w2 + 1], d3[x2]), x2++, w2--;
    else if (h4[j2] === a3[k2]) v3[k2] = u3(d3[j2], p4[k2]), v2(s5, d3[x2], d3[j2]), j2--, k2++;
    else if (void 0 === m4 && (m4 = u4(a3, k2, w2), y3 = u4(h4, x2, j2)), m4.has(h4[x2])) if (m4.has(h4[j2])) {
      const e5 = y3.get(a3[k2]), t6 = void 0 !== e5 ? d3[e5] : null;
      if (null === t6) {
        const e6 = v2(s5, d3[x2]);
        u3(e6, p4[k2]), v3[k2] = e6;
      } else v3[k2] = u3(t6, p4[k2]), v2(s5, d3[x2], t6), d3[e5] = null;
      k2++;
    } else h3(d3[j2]), j2--;
    else h3(d3[x2]), x2++;
    for (; k2 <= w2; ) {
      const e5 = v2(s5, v3[w2 + 1]);
      u3(e5, p4[k2]), v3[k2++] = e5;
    }
    for (; x2 <= j2; ) {
      const e5 = d3[x2++];
      null !== e5 && h3(e5);
    }
    return this.ut = a3, p3(s5, v3), E;
  }
});

// lit-html/directives/style-map.js
var n5 = "important";
var i6 = " !" + n5;
var o6 = e4(class extends i4 {
  constructor(t5) {
    if (super(t5), t5.type !== t3.ATTRIBUTE || "style" !== t5.name || t5.strings?.length > 2) throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.");
  }
  render(t5) {
    return Object.keys(t5).reduce((e5, r6) => {
      const s5 = t5[r6];
      return null == s5 ? e5 : e5 + `${r6 = r6.includes("-") ? r6 : r6.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g, "-$&").toLowerCase()}:${s5};`;
    }, "");
  }
  update(e5, [r6]) {
    const { style: s5 } = e5.element;
    if (void 0 === this.ft) return this.ft = new Set(Object.keys(r6)), this.render(r6);
    for (const t5 of this.ft) null == r6[t5] && (this.ft.delete(t5), t5.includes("-") ? s5.removeProperty(t5) : s5[t5] = null);
    for (const t5 in r6) {
      const e6 = r6[t5];
      if (null != e6) {
        this.ft.add(t5);
        const r7 = "string" == typeof e6 && e6.endsWith(i6);
        t5.includes("-") || r7 ? s5.setProperty(t5, r7 ? e6.slice(0, -11) : e6, r7 ? n5 : "") : s5[t5] = e6;
      }
    }
    return E;
  }
});

// @erplora/outfitkit/dist/shared/ion-tone.js
var DEFAULT_HEX = {
  primary: "#0054e9",
  secondary: "#0163aa",
  tertiary: "#6030ff",
  success: "#2dd55b",
  warning: "#ffc409",
  danger: "#c5000f",
  light: "#f4f5f8",
  medium: "#636469",
  dark: "#222428"
};
var DEFAULT_CONTRAST = {
  primary: "#fff",
  secondary: "#fff",
  tertiary: "#fff",
  success: "#000",
  warning: "#000",
  danger: "#fff",
  light: "#000",
  medium: "#fff",
  dark: "#fff"
};
var TONE_NAME = /^[a-z][a-z0-9-]*$/;
function tokenChain(okName, ionName, hex) {
  return `var(--ok-${okName}, var(--ion-color-${ionName}${hex ? `, ${hex}` : ""}))`;
}
function ionTone(tone, variant) {
  if (!tone || !TONE_NAME.test(tone)) return void 0;
  const value = tokenChain(tone, tone, DEFAULT_HEX[tone]);
  switch (variant) {
    case "text":
      return `color: ${value};`;
    case "clear":
      return `--color: ${value};`;
    case "outline":
      return `--color: ${value}; --border-color: ${value}; --background-activated: ${value}; --background-focused: ${value};`;
    case "solid": {
      const contrast = tokenChain(`${tone}-contrast`, `${tone}-contrast`, DEFAULT_CONTRAST[tone]);
      return `--background: ${value}; --color: ${contrast}; --background-hover: var(--ion-color-${tone}-tint, ${value}); --background-activated: var(--ion-color-${tone}-shade, ${value}); --background-focused: var(--ion-color-${tone}-shade, ${value});`;
    }
  }
}

// @erplora/outfitkit/dist/shared/icons.js
var rawAdd = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M256 112v288m144-144H112"/></svg>';
var rawAlertCircle = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="currentColor" d="M256 48C141.31 48 48 141.31 48 256s93.31 208 208 208s208-93.31 208-208S370.69 48 256 48m0 319.91a20 20 0 1 1 20-20a20 20 0 0 1-20 20m21.72-201.15l-5.74 122a16 16 0 0 1-32 0l-5.74-121.94v-.05a21.74 21.74 0 1 1 43.44 0Z"/></svg>';
var rawAlertCircleOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="32" d="M448 256c0-106-86-192-192-192S64 150 64 256s86 192 192 192s192-86 192-192Z"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M250.26 166.05L256 288l5.73-121.95a5.74 5.74 0 0 0-5.79-6h0a5.74 5.74 0 0 0-5.68 6"/><path fill="currentColor" d="M256 367.91a20 20 0 1 1 20-20a20 20 0 0 1-20 20"/></svg>';
var rawAppsOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><rect width="80" height="80" x="64" y="64" fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="32" rx="40" ry="40"/><rect width="80" height="80" x="216" y="64" fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="32" rx="40" ry="40"/><rect width="80" height="80" x="368" y="64" fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="32" rx="40" ry="40"/><rect width="80" height="80" x="64" y="216" fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="32" rx="40" ry="40"/><rect width="80" height="80" x="216" y="216" fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="32" rx="40" ry="40"/><rect width="80" height="80" x="368" y="216" fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="32" rx="40" ry="40"/><rect width="80" height="80" x="64" y="368" fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="32" rx="40" ry="40"/><rect width="80" height="80" x="216" y="368" fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="32" rx="40" ry="40"/><rect width="80" height="80" x="368" y="368" fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="32" rx="40" ry="40"/></svg>';
var rawArchiveOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M80 152v256a40.12 40.12 0 0 0 40 40h272a40.12 40.12 0 0 0 40-40V152"/><rect width="416" height="80" x="48" y="64" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="32" rx="28" ry="28"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="m320 304l-64 64l-64-64m64 41.89V224"/></svg>';
var rawArrowRedoOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="32" d="M448 256L272 88v96C103.57 184 64 304.77 64 424c48.61-62.24 91.6-96 208-96v96Z"/></svg>';
var rawArrowUndoOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="32" d="M240 424v-96c116.4 0 159.39 33.76 208 96c0-119.23-39.57-240-208-240V88L64 256Z"/></svg>';
var rawBackspaceOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="32" d="M135.19 390.14a28.8 28.8 0 0 0 21.68 9.86h246.26A29 29 0 0 0 432 371.13V140.87A29 29 0 0 0 403.13 112H156.87a28.84 28.84 0 0 0-21.67 9.84L46.33 256l88.86 134.11Z"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M336.67 192.33L206.66 322.34m130.01 0L206.66 192.33m130.01 0L206.66 322.34m130.01 0L206.66 192.33"/></svg>';
var rawCalendarOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><rect width="416" height="384" x="48" y="80" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="32" rx="48"/><circle cx="296" cy="232" r="24" fill="currentColor"/><circle cx="376" cy="232" r="24" fill="currentColor"/><circle cx="296" cy="312" r="24" fill="currentColor"/><circle cx="376" cy="312" r="24" fill="currentColor"/><circle cx="136" cy="312" r="24" fill="currentColor"/><circle cx="216" cy="312" r="24" fill="currentColor"/><circle cx="136" cy="392" r="24" fill="currentColor"/><circle cx="216" cy="392" r="24" fill="currentColor"/><circle cx="296" cy="392" r="24" fill="currentColor"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M128 48v32m256-32v32"/><path fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="32" d="M464 160H48"/></svg>';
var rawCheckmarkCircle = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="currentColor" d="M256 48C141.31 48 48 141.31 48 256s93.31 208 208 208s208-93.31 208-208S370.69 48 256 48m108.25 138.29l-134.4 160a16 16 0 0 1-12 5.71h-.27a16 16 0 0 1-11.89-5.3l-57.6-64a16 16 0 1 1 23.78-21.4l45.29 50.32l122.59-145.91a16 16 0 0 1 24.5 20.58"/></svg>';
var rawCheckmarkOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M416 128L192 384l-96-96"/></svg>';
var rawChevronBack = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="48" d="M328 112L184 256l144 144"/></svg>';
var rawChevronBackOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="48" d="M328 112L184 256l144 144"/></svg>';
var rawChevronDownOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="48" d="m112 184l144 144l144-144"/></svg>';
var rawChevronForward = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="48" d="m184 112l144 144l-144 144"/></svg>';
var rawChevronForwardOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="48" d="m184 112l144 144l-144 144"/></svg>';
var rawChevronUpOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="48" d="m112 328l144-144l144 144"/></svg>';
var rawClose = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="currentColor" d="m289.94 256l95-95A24 24 0 0 0 351 127l-95 95l-95-95a24 24 0 0 0-34 34l95 95l-95 95a24 24 0 1 0 34 34l95-95l95 95a24 24 0 0 0 34-34Z"/></svg>';
var rawCloseOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M368 368L144 144m224 0L144 368"/></svg>';
var rawCloudUploadOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M320 367.79h76c55 0 100-29.21 100-83.6s-53-81.47-96-83.6c-8.89-85.06-71-136.8-144-136.8c-69 0-113.44 45.79-128 91.2c-60 5.7-112 43.88-112 106.4s54 106.4 120 106.4h56"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="m320 255.79l-64-64l-64 64m64 192.42V207.79"/></svg>';
var rawCreateOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M384 224v184a40 40 0 0 1-40 40H104a40 40 0 0 1-40-40V168a40 40 0 0 1 40-40h167.48"/><path fill="currentColor" d="M459.94 53.25a16.06 16.06 0 0 0-23.22-.56L424.35 65a8 8 0 0 0 0 11.31l11.34 11.32a8 8 0 0 0 11.34 0l12.06-12c6.1-6.09 6.67-16.01.85-22.38M399.34 90L218.82 270.2a9 9 0 0 0-2.31 3.93L208.16 299a3.91 3.91 0 0 0 4.86 4.86l24.85-8.35a9 9 0 0 0 3.93-2.31L422 112.66a9 9 0 0 0 0-12.66l-9.95-10a9 9 0 0 0-12.71 0"/></svg>';
var rawContractOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M304 416V304h112m-101.8 10.23L432 432M208 96v112H96m101.8-10.23L80 80m336 128H304V96m10.23 101.8L432 80M96 304h112v112m-10.23-101.8L80 432"/></svg>';
var rawDocumentAttachOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M208 64h66.75a32 32 0 0 1 22.62 9.37l141.26 141.26a32 32 0 0 1 9.37 22.62V432a48 48 0 0 1-48 48H192a48 48 0 0 1-48-48V304"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M288 72v120a32 32 0 0 0 32 32h120"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-miterlimit="10" stroke-width="32" d="M160 80v152a23.69 23.69 0 0 1-24 24c-12 0-24-9.1-24-24V88c0-30.59 16.57-56 48-56s48 24.8 48 55.38v138.75c0 43-27.82 77.87-72 77.87s-72-34.86-72-77.87V144"/></svg>';
var rawDocumentOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="32" d="M416 221.25V416a48 48 0 0 1-48 48H144a48 48 0 0 1-48-48V96a48 48 0 0 1 48-48h98.75a32 32 0 0 1 22.62 9.37l141.26 141.26a32 32 0 0 1 9.37 22.62Z"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M256 56v120a32 32 0 0 0 32 32h120"/></svg>';
var rawDocumentTextOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="32" d="M416 221.25V416a48 48 0 0 1-48 48H144a48 48 0 0 1-48-48V96a48 48 0 0 1 48-48h98.75a32 32 0 0 1 22.62 9.37l141.26 141.26a32 32 0 0 1 9.37 22.62Z"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M256 56v120a32 32 0 0 0 32 32h120m-232 80h160m-160 80h160"/></svg>';
var rawDownloadOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M336 176h40a40 40 0 0 1 40 40v208a40 40 0 0 1-40 40H136a40 40 0 0 1-40-40V216a40 40 0 0 1 40-40h40"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="m176 272l80 80l80-80M256 48v288"/></svg>';
var rawEllipsisVertical = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><circle cx="256" cy="256" r="48" fill="currentColor"/><circle cx="256" cy="416" r="48" fill="currentColor"/><circle cx="256" cy="96" r="48" fill="currentColor"/></svg>';
var rawExpandOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M432 320v112H320m101.8-10.23L304 304M80 192V80h112M90.2 90.23L208 208M320 80h112v112M421.77 90.2L304 208M192 432H80V320m10.23 101.8L208 304"/></svg>';
var rawFileTrayOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="32" d="M384 80H128c-26 0-43 14-48 40L48 272v112a48.14 48.14 0 0 0 48 48h320a48.14 48.14 0 0 0 48-48V272l-32-152c-5-27-23-40-48-40Z"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M48 272h144m128 0h144m-272 0a64 64 0 0 0 128 0"/></svg>';
var rawFolderOpenOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M64 192v-72a40 40 0 0 1 40-40h75.89a40 40 0 0 1 22.19 6.72l27.84 18.56a40 40 0 0 0 22.19 6.72H408a40 40 0 0 1 40 40v40"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M479.9 226.55L463.68 392a40 40 0 0 1-39.93 40H88.25a40 40 0 0 1-39.93-40L32.1 226.55A32 32 0 0 1 64 192h384.1a32 32 0 0 1 31.8 34.55"/></svg>';
var rawInformationCircle = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="currentColor" d="M256 56C145.72 56 56 145.72 56 256s89.72 200 200 200s200-89.72 200-200S366.28 56 256 56m0 82a26 26 0 1 1-26 26a26 26 0 0 1 26-26m48 226h-88a16 16 0 0 1 0-32h28v-88h-16a16 16 0 0 1 0-32h32a16 16 0 0 1 16 16v104h28a16 16 0 0 1 0 32"/></svg>';
var rawMenuOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-miterlimit="10" stroke-width="32" d="M80 160h352M80 256h352M80 352h352"/></svg>';
var rawNotificationsOffOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M128.51 204.59q-.37 6.15-.37 12.76C128.14 304 110 320 84.33 351.43C73.69 364.45 83 384 101.62 384H320m94.5-48.7c-18.48-23.45-30.62-47.05-30.62-118c0-79.3-40.52-107.57-73.88-121.3c-4.43-1.82-8.6-6-9.95-10.55C294.21 65.54 277.82 48 256 48s-38.2 17.55-44 37.47c-1.35 4.6-5.52 8.71-10 10.53a150 150 0 0 0-18 8.79M320 384v16a64 64 0 0 1-128 0v-16"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-miterlimit="10" stroke-width="32" d="M448 448L64 64"/></svg>';
var rawOpenOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M384 224v184a40 40 0 0 1-40 40H104a40 40 0 0 1-40-40V168a40 40 0 0 1 40-40h167.48M336 64h112v112M224 288L440 72"/></svg>';
var rawPlayOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="32" d="M112 111v290c0 17.44 17 28.52 31 20.16l247.9-148.37c12.12-7.25 12.12-26.33 0-33.58L143 90.84c-14-8.36-31 2.72-31 20.16Z"/></svg>';
var rawRemove = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M400 256H112"/></svg>';
var rawSearchOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="32" d="M221.09 64a157.09 157.09 0 1 0 157.09 157.09A157.1 157.1 0 0 0 221.09 64Z"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-miterlimit="10" stroke-width="32" d="M338.29 338.29L448 448"/></svg>';
var rawSend = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="currentColor" d="m476.59 227.05l-.16-.07L49.35 49.84A23.56 23.56 0 0 0 27.14 52A24.65 24.65 0 0 0 16 72.59v113.29a24 24 0 0 0 19.52 23.57l232.93 43.07a4 4 0 0 1 0 7.86L35.53 303.45A24 24 0 0 0 16 327v113.31A23.57 23.57 0 0 0 26.59 460a23.94 23.94 0 0 0 13.22 4a24.55 24.55 0 0 0 9.52-1.93L476.4 285.94l.19-.09a32 32 0 0 0 0-58.8"/></svg>';
var rawSwapVerticalOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M464 208L352 96L240 208m112-94.87V416M48 304l112 112l112-112m-112 94V96"/></svg>';
var rawTrashOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="m112 112l20 320c.95 18.49 14.4 32 32 32h184c17.67 0 30.87-13.51 32-32l20-320"/><path fill="currentColor" stroke="currentColor" stroke-linecap="round" stroke-miterlimit="10" stroke-width="32" d="M80 112h352"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M192 112V72h0a23.93 23.93 0 0 1 24-24h80a23.93 23.93 0 0 1 24 24h0v40m-64 64v224m-72-224l8 224m136-224l-8 224"/></svg>';
var rawTrendingDown = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M352 368h112V256"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="m48 144l121.37 121.37a32 32 0 0 0 45.26 0l50.74-50.74a32 32 0 0 1 45.26 0L448 352"/></svg>';
var rawTrendingUp = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M352 144h112v112"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="m48 368l121.37-121.37a32 32 0 0 1 45.26 0l50.74 50.74a32 32 0 0 0 45.26 0L448 160"/></svg>';
var rawVolumeHighOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M126 192H56a8 8 0 0 0-8 8v112a8 8 0 0 0 8 8h69.65a15.93 15.93 0 0 1 10.14 3.54l91.47 74.89A8 8 0 0 0 240 392V120a8 8 0 0 0-12.74-6.43l-91.47 74.89A15 15 0 0 1 126 192m194 128c9.74-19.38 16-40.84 16-64c0-23.48-6-44.42-16-64m48 176c19.48-33.92 32-64.06 32-112s-12-77.74-32-112m48 272c30-46 48-91.43 48-160s-18-113-48-160"/></svg>';
var rawVolumeLowOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32" d="M189.65 192H120a8 8 0 0 0-8 8v112a8 8 0 0 0 8 8h69.65a16 16 0 0 1 10.14 3.63l91.47 75a8 8 0 0 0 12.74-6.46V119.83a8 8 0 0 0-12.74-6.44l-91.47 75a16 16 0 0 1-10.14 3.61M384 320c9.74-19.41 16-40.81 16-64c0-23.51-6-44.4-16-64"/></svg>';
var rawVolumeMuteOutline = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-miterlimit="10" stroke-width="32" d="M416 432L64 80"/><path fill="currentColor" d="M224 136.92v33.8a4 4 0 0 0 1.17 2.82l24 24a4 4 0 0 0 6.83-2.82v-74.15a24.53 24.53 0 0 0-12.67-21.72a23.91 23.91 0 0 0-25.55 1.83a8 8 0 0 0-.66.51l-31.94 26.15a4 4 0 0 0-.29 5.92l17.05 17.06a4 4 0 0 0 5.37.26Zm0 238.16l-78.07-63.92a32 32 0 0 0-20.28-7.16H64v-96h50.72a4 4 0 0 0 2.82-6.83l-24-24a4 4 0 0 0-2.82-1.17H56a24 24 0 0 0-24 24v112a24 24 0 0 0 24 24h69.76l91.36 74.8a8 8 0 0 0 .66.51a23.93 23.93 0 0 0 25.85 1.69A24.49 24.49 0 0 0 256 391.45v-50.17a4 4 0 0 0-1.17-2.82l-24-24a4 4 0 0 0-6.83 2.82ZM352 256c0-24.56-5.81-47.88-17.75-71.27a16 16 0 0 0-28.5 14.54C315.34 218.06 320 236.62 320 256q0 4-.31 8.13a8 8 0 0 0 2.32 6.25l19.66 19.67a4 4 0 0 0 6.75-2A147 147 0 0 0 352 256m64 0c0-51.19-13.08-83.89-34.18-120.06a16 16 0 0 0-27.64 16.12C373.07 184.44 384 211.83 384 256c0 23.83-3.29 42.88-9.37 60.65a8 8 0 0 0 1.9 8.26l16.77 16.76a4 4 0 0 0 6.52-1.27C410.09 315.88 416 289.91 416 256"/><path fill="currentColor" d="M480 256c0-74.26-20.19-121.11-50.51-168.61a16 16 0 1 0-27 17.22C429.82 147.38 448 189.5 448 256c0 47.45-8.9 82.12-23.59 113a4 4 0 0 0 .77 4.55L443 391.39a4 4 0 0 0 6.4-1C470.88 348.22 480 307 480 256"/></svg>';
var rawWarning = '<svg viewBox="0 0 512 512" width="1.2em" height="1.2em" ><path fill="currentColor" d="M449.07 399.08L278.64 82.58c-12.08-22.44-44.26-22.44-56.35 0L51.87 399.08A32 32 0 0 0 80 446.25h340.89a32 32 0 0 0 28.18-47.17m-198.6-1.83a20 20 0 1 1 20-20a20 20 0 0 1-20 20m21.72-201.15l-5.74 122a16 16 0 0 1-32 0l-5.74-121.95a21.73 21.73 0 0 1 21.5-22.69h.21a21.74 21.74 0 0 1 21.73 22.7Z"/></svg>';
function bake(svg) {
  return `data:image/svg+xml;utf8,${svg}`;
}
var iconAdd = bake(rawAdd);
var iconAlertCircle = bake(rawAlertCircle);
var iconAlertCircleOutline = bake(rawAlertCircleOutline);
var iconAppsOutline = bake(rawAppsOutline);
var iconArchiveOutline = bake(rawArchiveOutline);
var iconArrowRedoOutline = bake(rawArrowRedoOutline);
var iconArrowUndoOutline = bake(rawArrowUndoOutline);
var iconBackspaceOutline = bake(rawBackspaceOutline);
var iconCalendarOutline = bake(rawCalendarOutline);
var iconCheckmarkCircle = bake(rawCheckmarkCircle);
var iconCheckmarkOutline = bake(rawCheckmarkOutline);
var iconChevronBack = bake(rawChevronBack);
var iconChevronBackOutline = bake(rawChevronBackOutline);
var iconChevronDownOutline = bake(rawChevronDownOutline);
var iconChevronForward = bake(rawChevronForward);
var iconChevronForwardOutline = bake(rawChevronForwardOutline);
var iconChevronUpOutline = bake(rawChevronUpOutline);
var iconClose = bake(rawClose);
var iconCloseOutline = bake(rawCloseOutline);
var iconCloudUploadOutline = bake(rawCloudUploadOutline);
var iconCreateOutline = bake(rawCreateOutline);
var iconDocumentAttachOutline = bake(rawDocumentAttachOutline);
var iconContractOutline = bake(rawContractOutline);
var iconDocumentOutline = bake(rawDocumentOutline);
var iconDocumentTextOutline = bake(rawDocumentTextOutline);
var iconDownloadOutline = bake(rawDownloadOutline);
var iconEllipsisVertical = bake(rawEllipsisVertical);
var iconExpandOutline = bake(rawExpandOutline);
var iconFileTrayOutline = bake(rawFileTrayOutline);
var iconFolderOpenOutline = bake(rawFolderOpenOutline);
var iconInformationCircle = bake(rawInformationCircle);
var iconMenuOutline = bake(rawMenuOutline);
var iconNotificationsOffOutline = bake(rawNotificationsOffOutline);
var iconOpenOutline = bake(rawOpenOutline);
var iconPlayOutline = bake(rawPlayOutline);
var iconRemove = bake(rawRemove);
var iconSearchOutline = bake(rawSearchOutline);
var iconSend = bake(rawSend);
var iconSwapVerticalOutline = bake(rawSwapVerticalOutline);
var iconTrashOutline = bake(rawTrashOutline);
var iconTrendingDown = bake(rawTrendingDown);
var iconTrendingUp = bake(rawTrendingUp);
var iconVolumeHighOutline = bake(rawVolumeHighOutline);
var iconVolumeLowOutline = bake(rawVolumeLowOutline);
var iconVolumeMuteOutline = bake(rawVolumeMuteOutline);
var iconWarning = bake(rawWarning);
var BY_NAME = {
  "add": iconAdd,
  "alert-circle": iconAlertCircle,
  "alert-circle-outline": iconAlertCircleOutline,
  "apps-outline": iconAppsOutline,
  "archive-outline": iconArchiveOutline,
  "arrow-redo-outline": iconArrowRedoOutline,
  "arrow-undo-outline": iconArrowUndoOutline,
  "backspace-outline": iconBackspaceOutline,
  "calendar-outline": iconCalendarOutline,
  "checkmark-circle": iconCheckmarkCircle,
  "checkmark-outline": iconCheckmarkOutline,
  "chevron-back": iconChevronBack,
  "chevron-back-outline": iconChevronBackOutline,
  "chevron-down-outline": iconChevronDownOutline,
  "chevron-forward": iconChevronForward,
  "chevron-forward-outline": iconChevronForwardOutline,
  "chevron-up-outline": iconChevronUpOutline,
  "close": iconClose,
  "close-outline": iconCloseOutline,
  "cloud-upload-outline": iconCloudUploadOutline,
  "create-outline": iconCreateOutline,
  "document-attach-outline": iconDocumentAttachOutline,
  "contract-outline": iconContractOutline,
  "document-outline": iconDocumentOutline,
  "document-text-outline": iconDocumentTextOutline,
  "download-outline": iconDownloadOutline,
  "ellipsis-vertical": iconEllipsisVertical,
  "expand-outline": iconExpandOutline,
  "file-tray-outline": iconFileTrayOutline,
  "folder-open-outline": iconFolderOpenOutline,
  "information-circle": iconInformationCircle,
  "menu-outline": iconMenuOutline,
  "notifications-off-outline": iconNotificationsOffOutline,
  "open-outline": iconOpenOutline,
  "play-outline": iconPlayOutline,
  "remove": iconRemove,
  "search-outline": iconSearchOutline,
  "send": iconSend,
  "swap-vertical-outline": iconSwapVerticalOutline,
  "trash-outline": iconTrashOutline,
  "trending-down": iconTrendingDown,
  "trending-up": iconTrendingUp,
  "volume-high-outline": iconVolumeHighOutline,
  "volume-low-outline": iconVolumeLowOutline,
  "volume-mute-outline": iconVolumeMuteOutline,
  "warning": iconWarning
};
function okIcon(value) {
  if (!value) return void 0;
  const trimmed = value.trimStart();
  if (trimmed.startsWith("<svg")) return bake(trimmed);
  return BY_NAME[value] ?? value;
}

// @erplora/outfitkit/dist/ok-data-table.js
var CSV_BOM = "\uFEFF";
var WINDOWS_1252_C1 = [
  8364,
  129,
  8218,
  402,
  8222,
  8230,
  8224,
  8225,
  710,
  8240,
  352,
  8249,
  338,
  141,
  381,
  143,
  144,
  8216,
  8217,
  8220,
  8221,
  8226,
  8211,
  8212,
  732,
  8482,
  353,
  8250,
  339,
  157,
  382,
  376
];
function decodeWindows1252(bytes) {
  let text3 = "";
  for (const byte of bytes) {
    text3 += String.fromCharCode(byte >= 128 && byte <= 159 ? WINDOWS_1252_C1[byte - 128] : byte);
  }
  return text3;
}
function decodeCsvBuffer(buf) {
  let text3;
  try {
    text3 = new TextDecoder("utf-8", { fatal: true }).decode(buf);
  } catch {
    text3 = decodeWindows1252(new Uint8Array(buf));
  }
  return text3.charCodeAt(0) === 65279 ? text3.slice(1) : text3;
}
var __defProp2 = Object.defineProperty;
var __decorateClass2 = (decorators, target, key, kind) => {
  var result = void 0;
  for (var i7 = decorators.length - 1, decorator; i7 >= 0; i7--)
    if (decorator = decorators[i7])
      result = decorator(target, key, result) || result;
  if (result) __defProp2(target, key, result);
  return result;
};
function decideRowActionsFit(input) {
  const { containerWidth, contentWidth, collapsed, decidedAtWidth } = input;
  if (!(containerWidth > 0)) return { collapsed, decidedAtWidth };
  if (containerWidth !== decidedAtWidth) {
    if (collapsed) return { collapsed: false, decidedAtWidth: containerWidth };
    return { collapsed: contentWidth > containerWidth, decidedAtWidth: containerWidth };
  }
  if (!collapsed && contentWidth > containerWidth) return { collapsed: true, decidedAtWidth };
  return { collapsed, decidedAtWidth };
}
var DEFAULT_LABELS = {
  search: "Search\u2026",
  empty: "No results",
  filters: "Filters",
  clear: "Clear",
  apply: "Apply",
  selected: "{n} selected",
  importCsv: "Import CSV",
  exportCsv: "Export CSV",
  add: "Add",
  moreActions: "More actions",
  rowsPerPage: "Rows per page",
  perPageShort: "{n} / page",
  viewList: "View as list",
  viewCards: "View as cards",
  columnsVisible: "Visible columns",
  columns: "Columns",
  actions: "Actions",
  close: "Close",
  newRecord: "New",
  form: "Form",
  filterPlaceholder: "Filter\u2026",
  from: "From",
  to: "To",
  fromOf: "{label} from",
  toOf: "{label} to",
  gte: "\u2265",
  lte: "\u2264",
  noValues: "No values",
  selectAll: "Select all",
  selectRow: "Select row",
  select: "Select",
  showing: "Showing {from}\u2013{to} of",
  recordSingular: "record",
  recordPlural: "records",
  loadMore: "Load more",
  noMatches: "No results match your search or filters",
  showAll: "Show all"
};
var ES_LABELS = {
  search: "Buscar\u2026",
  empty: "Sin resultados",
  filters: "Filtros",
  clear: "Limpiar",
  apply: "Aplicar",
  selected: "{n} seleccionados",
  importCsv: "Importar CSV",
  exportCsv: "Exportar CSV",
  add: "A\xF1adir",
  moreActions: "M\xE1s acciones",
  rowsPerPage: "Filas por p\xE1gina",
  perPageShort: "{n} / p\xE1g.",
  viewList: "Vista lista",
  viewCards: "Vista tarjetas",
  columnsVisible: "Columnas visibles",
  columns: "Columnas",
  actions: "Acciones",
  close: "Cerrar",
  newRecord: "Nuevo",
  form: "Formulario",
  filterPlaceholder: "Filtrar\u2026",
  from: "Desde",
  to: "Hasta",
  fromOf: "{label} desde",
  toOf: "{label} hasta",
  gte: "\u2265",
  lte: "\u2264",
  noValues: "Sin valores",
  selectAll: "Seleccionar todo",
  selectRow: "Seleccionar fila",
  select: "Seleccionar",
  showing: "Mostrando {from}\u2013{to} de",
  recordSingular: "registro",
  recordPlural: "registros",
  loadMore: "Cargar m\xE1s",
  noMatches: "Ning\xFAn resultado coincide con la b\xFAsqueda o los filtros",
  showAll: "Mostrar todo"
};
var _OkDataTable = class _OkDataTable2 extends i3 {
  constructor() {
    super(...arguments);
    this.columns = [];
    this.rows = [];
    this.searchKeys = [];
    this.rowKeyField = "id";
    this.pageSize = 10;
    this.labels = {};
    this.actions = [];
    this.addable = false;
    this.pageSizeOptions = [10, 25, 50, 100];
    this.fill = false;
    this.columnPicker = true;
    this.csv = false;
    this.csvName = "export.csv";
    this.serverSide = false;
    this.total = 0;
    this.page = 0;
    this.searchable = false;
    this.sortDir = "asc";
    this.filterValues = {};
    this.title = "";
    this.views = false;
    this.exportable = false;
    this.importable = false;
    this.columnSelector = false;
    this.rowClickable = false;
    this.selectable = false;
    this.inlineFilters = false;
    this.menuActions = [];
    this.q = "";
    this.clientPage = 0;
    this.clientPageSize = 0;
    this.mobileShown = 0;
    this.clientSort = "";
    this.clientSortDir = "asc";
    this.clientFilters = {};
    this.filterDraft = {};
    this.serverFilters = {};
    this.panel = "none";
    this.viewMode = "table";
    this.viewChosenByUser = false;
    this.isMobile = false;
    this.xOverflow = false;
    this.actionsTrackPx = 0;
    this.rowActionsCollapsed = false;
    this.fitDecidedAtWidth = -1;
    this.rowMenuOpen = false;
    this.hiddenKeys = /* @__PURE__ */ new Set();
    this.internalSelection = /* @__PURE__ */ new Set();
    this.menuOpen = false;
    this.onLocaleChanged = () => this.requestUpdate();
    this.onWindowResize = () => {
      this.measureXOverflow();
      this.measureRowActionsFit();
    };
    this.onSearch = (ev) => {
      const value = ev.target.value ?? "";
      if (this.serverSide) {
        this.q = value;
        this.emit("searchChange", value);
      } else {
        this.q = value;
        this.clientPage = 0;
        this.mobileShown = 0;
      }
    };
  }
  static {
    this.styles = i`
    :host {
      /* Vars overridable (estilo Ionic), default = cadena --ok-* → --ion-* → hex */
      --background: var(--ok-surface, var(--ion-card-background, var(--ion-background-color, #ffffff)));
      --color: var(--ok-text, var(--ion-text-color, #1c1b17));
      --color-muted: var(--ok-muted, var(--ion-color-medium, rgba(var(--ion-text-color-rgb, 24, 24, 27), 0.55)));
      --border-color: var(--ok-border, var(--ion-color-step-150, rgba(var(--ion-text-color-rgb, 24, 24, 27), 0.12)));
      --border-color-soft: var(--ok-border-soft, var(--ion-color-step-100, rgba(var(--ion-text-color-rgb, 24, 24, 27), 0.07)));
      /* Borde más marcado para los controles de la toolbar (selects/pastilla de fechas), para que se
       * distingan como controles en claro y oscuro aunque el lienzo y la superficie casi no contrasten. */
      --control-border: color-mix(in srgb, var(--color) 22%, transparent);
      /* Relieve de cabecera/pie: step-100 (definido en claro y oscuro) → contraste con el lienzo. */
      --header-background: var(--ok-surface-2, var(--ion-color-step-100, rgba(var(--ion-text-color-rgb, 24, 24, 27), 0.04)));
      --row-hover: var(--ok-row-hover, var(--ion-color-step-50, rgba(var(--ion-text-color-rgb, 24, 24, 27), 0.03)));
      --primary: var(--ok-primary, var(--ion-color-primary, #3880ff));
      --primary-contrast: var(--ok-primary-contrast, var(--ion-color-primary-contrast, #ffffff));
      --border-radius: var(--ok-radius, 16px);
      --font: var(--ok-font, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif);

      display: block;
      color: var(--color);
      font-family: var(--font);
    }
    * { box-sizing: border-box; }
    .card {
      position: relative;
      display: flex;
      flex-direction: column;
      /* Flat: sin borde ni elevación (directiva 2026-06-09). */
      border: 0;
      border-radius: var(--border-radius);
      overflow: hidden;
      background: var(--background);
      box-shadow: none;
    }

    /* Panel lateral derecho (drawer) DENTRO de la tabla: filtros / alta-edición. Base (sin media):
       overlay absoluto — es lo que había hasta #75 y lo que ve un navegador sin media queries. */
    .tk-scrim { position: absolute; inset: 0; background: rgba(0, 0, 0, 0.18); z-index: 19; }
    .drawer { position: absolute; top: 0; right: 0; height: 100%; width: 340px; max-width: 88%;
      background: var(--background); border-left: 1px solid var(--border-color);
      display: flex; flex-direction: column; z-index: 20;
      animation: tk-slide-in 0.18s ease; }
    @keyframes tk-slide-in { from { transform: translateX(100%); } to { transform: translateX(0); } }
    /* #75 — El panel EMPUJA en escritorio y es HOJA COMPLETA en móvil; nunca tapa a medias.
       Medido en el hub (Servicios/Citas): a 1440 el overlay de 340px se pintaba ENCIMA de
       «Duración», «Acciones» y el selector de columnas, con el 90% de la tabla vacío a la
       izquierda; a 390 dejaba una tira de 45px de tabla (media lupa, medio «Co…») que hacía
       parecer el formulario un pop-up mal puesto. Square Dashboard reduce la tabla con un panel
       fijo; Fresha/Shopify/Odoo abren una hoja a pantalla completa en móvil.
       ≥ 834px: mientras hay panel, .card pasa a rejilla de DOS columnas (tabla | panel 360px):
       la tabla se estrecha (ya sabe hacer scroll-x, #67) y nada queda tapado. */
    @media (min-width: 834px) {
      .card.has-panel { display: grid; grid-template-columns: minmax(0, 1fr) 360px; grid-template-rows: auto minmax(0, 1fr) auto; }
      .card.has-panel > .bar { grid-column: 1; grid-row: 1; }
      .card.has-panel > .scroll, .card.has-panel > .cards-grid, .card.has-panel > .empty { grid-column: 1; grid-row: 2; min-height: 0; overflow: auto; }
      .card.has-panel > .pager { grid-column: 1; grid-row: 3; }
      .card.has-panel > .drawer { position: static; grid-column: 2; grid-row: 1 / -1; width: auto; max-width: none; height: auto; min-height: 0; animation: none; }
      .card.has-panel > .tk-scrim { display: none; }
    }
    /* < 834px: hoja a pantalla completa con su cabecera (título + Cerrar); sin tira residual.
       position:fixed dentro de ion-content se ancla al área de contenido (contain), que es justo el hueco
       bajo la cabecera de la app: el usuario conserva el título de la página. */
    @media (max-width: 833.98px) {
      .drawer { position: fixed; inset: 0; top: var(--ok-sheet-top, 0px); width: 100%; max-width: none; height: auto; border-left: 0; z-index: 1000; }
      .tk-scrim { display: none; }
    }
    .drawer .dh { flex: 0 0 auto; display: flex; align-items: center; justify-content: space-between;
      padding: 0.6rem 0.5rem 0.6rem 1rem; border-bottom: 1px solid var(--border-color); font-size: 1rem; }
    .drawer .db { flex: 1 1 auto; min-height: 0; overflow: auto; padding: 1rem; display: flex; flex-direction: column; gap: 0.85rem; }
    .fblock { display: flex; flex-direction: column; gap: 0.45rem; }
    .flabel { font-size: 13px; font-weight: 500; color: var(--color); }
    .frange { display: flex; gap: 0.5rem; }
    /* Filtros cliente: multi-select con ion-select (ventana flotante de Ionic) + rango de fechas. */
    .daterange { display: flex; gap: 0.6rem; }
    .daterange ion-input { flex: 1; }
    /* Pie del drawer de filtros: Limpiar / Aplicar. */
    .df { flex: 0 0 auto; display: flex; align-items: center; justify-content: flex-end; gap: 0.4rem; padding: 0.6rem 0.85rem; border-top: 1px solid var(--border-color); }
    .df .df-clear { margin-right: auto; }

    /* Modo fill: la tabla ocupa el alto del contenedor; filas con scroll interno; pager fijo. */
    :host([fill]) { display: flex; flex-direction: column; height: 100%; min-height: 0; }
    :host([fill]) .card { flex: 1 1 auto; min-height: 0; }
    :host([fill]) .bar, :host([fill]) .panel, :host([fill]) .pager { flex: 0 0 auto; }
    :host([fill]) .scroll, :host([fill]) .cards-grid { flex: 1 1 auto; min-height: 0; overflow: auto; }
    /* Sin filas, renderTable/renderCards devuelven SOLO el bloque .empty (sin .scroll). En modo
       fill hay que estirarlo para que ocupe el hueco entre toolbar y pager y centre su contenido
       (icono + mensaje) en vertical; si no, queda pegado arriba con el pager a media altura. */
    :host([fill]) .empty { flex: 1 1 auto; min-height: 0; }

    /* ── Topbar / cabecera (relieve) ─────────────────────────────────────────────────────── */
    .bar { display: flex; flex-direction: column; gap: 0.6rem; padding: 0.65rem 1rem; border-bottom: 1px solid var(--border-color); background: var(--header-background); }
    /* Toolbar CONSOLIDADA: TODOS los controles son hijos directos de UNA sola fila flex que
     * envuelve ELEMENTO A ELEMENTO (no por bloques): caben en una línea → una línea; los que no
     * caben bajan a la(s) línea(s) que hagan falta. El cluster derecho se empuja al borde con
     * .tk-spacer (hueco flexible) solo cuando todo cabe en una línea; al envolver, el spacer se
     * oculta y todo se apila a la izquierda.
     * ORDEN CANÓNICO (2026-06-22, izquierda→derecha): [buscador] · [filtros en línea] · ‹spacer› ·
     * [SELECTORES: columnas → filas/página] · [BOTONES: vistas → filtros(funnel) → import → export →
     * alta → ⋮ → acción primaria]. Es decir: buscador al inicio, filtros en medio, y al final los
     * selectores (columnas, luego «N por página») seguidos de los botones de acción. */
    .bar-main { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; }
    .bar-main > ion-button { --padding-start: 0.5rem; --padding-end: 0.5rem; margin: 0; }
    /* Spacer que absorbe el hueco libre en pantallas anchas (empuja el cluster derecho al borde).
     * Se oculta por debajo de 1024px para que, al envolver, los controles se apilen a la izquierda. */
    .tk-spacer { flex: 1 1 0; min-width: 0; align-self: stretch; }
    @media (max-width: 1024px) { .tk-spacer { display: none; } }
    /* Buscador a ancho completo (línea propia) en móvil; el resto envuelve debajo. */
    @media (max-width: 640px) { .search { flex-basis: 100%; max-width: none; } }
    .title-wrap { display: flex; align-items: baseline; gap: 0.5rem; }
    .title { font-size: 15px; font-weight: 600; line-height: 1; margin: 0; }
    .title-count { font-size: 12px; font-weight: 500; color: var(--color-muted); }

    /* Botón de herramienta cuadrado (filtros/import/export), look del Hub: 36×36, badge contador. */
    .toolbtn { position: relative; --padding-start: 0; --padding-end: 0; --border-radius: 10px; width: 36px; height: 36px; margin: 0; }
    .toolbtn .badge { position: absolute; top: -5px; right: -5px; min-width: 16px; height: 16px; padding: 0 3px; border-radius: 999px; background: var(--primary); color: var(--primary-contrast); font-size: 10px; font-weight: 700; line-height: 16px; text-align: center; pointer-events: none; }

    /* Buscador (caja con icono + limpiar), look del Hub. No crece (el spacer se queda el hueco);
     * puede encoger hasta min-width y, por debajo, envuelve. */
    .search { flex: 0 1 22rem; min-width: 12rem; max-width: 24rem; }
    ion-searchbar { --background: var(--background); --border-radius: 10px; padding: 0; min-height: 36px; }
    /* Flat: el buscador quita borde y elevación vía la clase específica de Ionic 'ion-no-border'.
     * (La regla global de Ionic para .ion-no-border no cruza el Shadow DOM, así que la
     * reimplementamos aquí dentro: --box-shadow controla la elevación; ::part(native) el borde.) */
    ion-searchbar.ion-no-border { --box-shadow: none; }
    ion-searchbar.ion-no-border::part(native) { border: none; box-shadow: none; }

    /* Toggle de vista lista/tarjetas (segmento) */
    .viewseg { display: inline-flex; align-items: center; gap: 2px; padding: 2px; border: 1px solid var(--border-color); border-radius: 10px; background: var(--background); }
    .viewseg ion-button { --border-radius: 7px; }

    /* Botón primario (primaryAction) */
    .primary-btn { --background: var(--primary); --color: var(--primary-contrast); }
    /* #76 — El alta en MÓVIL: botón primario CON etiqueta y área táctil de 44px, en vez del «+»
       icónico de 36px al final de la barra. Fresha/Square/Shopify POS ponen la acción primaria
       de la lista como botón visible con texto (o FAB), nunca como icono anónimo.
       #113 — Y en ESCRITORIO igual: Odoo («New»), Business Central, Shopify («Add product»),
       WooCommerce, Lightspeed y Fresha rotulan y rellenan la acción principal de un listado; NN/g
       reserva el botón sin rótulo para lo universal (buscar, cerrar). Aquí solo cambia la ALTURA:
       36px para alinear con .toolbtn y el buscador, y los 44px táctiles vuelven abajo con el
       resto de objetivos de puntero grueso. */
    .add-btn { min-height: 36px; --border-radius: 10px; --padding-start: 0.9rem; --padding-end: 1rem; margin: 0; font-weight: 600; }
    .add-btn ion-icon { margin-inline-end: 0.35rem; }

    /* Selects de la toolbar: fondo + borde visibles (como el buscador y la pastilla de fechas) para
     * que se distingan como controles en claro y oscuro (sin fondo eran invisibles en dark). */
    .tk-cols { min-width: 6.5rem; max-width: 9rem; min-height: 38px; font-size: 13px; background: var(--background); color: var(--color); border: 1px solid var(--control-border); border-radius: 10px; --padding-start: 0.6rem; --padding-end: 0.4rem; --padding-top: 0.3rem; --padding-bottom: 0.3rem; }
    .vsep { width: 1px; align-self: stretch; background: var(--border-color); margin: 0.3rem 0.25rem; }

    /* Selector de filas/página en la toolbar (consolidado) */
    /* max-width: ion-select es display:block (sin core.css el host estira a la
     * línea entera cuando .bar-end hace wrap) — se capa como .tk-cols. */
    .tk-psize { min-width: 4.25rem; max-width: 5.5rem; min-height: 38px; font-size: 13px; background: var(--background); color: var(--color); border: 1px solid var(--control-border); border-radius: 10px; --padding-start: 0.6rem; --padding-end: 0.4rem; --padding-top: 0.35rem; --padding-bottom: 0.35rem; }

    /* Filtros EN LÍNEA en la toolbar (select / rango de fechas) */
    .tk-filter { min-width: 8.5rem; max-width: 13rem; min-height: 38px; font-size: 13px; background: var(--background); color: var(--color); border: 1px solid var(--control-border); border-radius: 10px; --padding-start: 0.7rem; --padding-end: 0.5rem; --padding-top: 0.35rem; --padding-bottom: 0.35rem; }
    .tk-daterange { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.3rem 0.6rem; min-height: 38px; border: 1px solid var(--control-border); border-radius: 10px; background: var(--background); color: var(--color-muted); font-size: 13px; }
    .tk-daterange ion-icon { font-size: 15px; flex: 0 0 auto; }
    .tk-daterange ion-input { --background: transparent; --padding-start: 0; --padding-end: 0; --padding-top: 2px; --padding-bottom: 2px; --color: var(--color); min-height: 26px; width: 6.8rem; font-size: 13px; }
    .tk-daterange .arr { color: var(--color-muted); }

    /* Barra contextual de selección */
    .selbar { display: flex; align-items: center; gap: 0.6rem; padding: 0.4rem 0.7rem; border-radius: 10px;
      font-size: 13px; color: var(--primary);
      background: color-mix(in srgb, var(--primary) 12%, transparent); }
    .selbar .sel-clear { margin-left: auto; display: inline-flex; align-items: center; gap: 0.25rem; cursor: pointer; font-weight: 500; color: inherit; background: none; border: 0; font: inherit; }
    .selbar .sel-clear:hover { text-decoration: underline; }

    /* Acordeones (alta / filtros en modo tarjetas) */
    .panel { padding: 0.85rem 1rem; border-bottom: 1px solid var(--border-color); background: var(--header-background); }
    .filters-panel { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.6rem; }

    /* ── Vista lista en CSS GRID (no <table>): permite ancho por columna ──────────────────── */
    /* #67 — La barra horizontal es PERMANENTE cuando hay desbordamiento: la overlay de macOS se
       esconde a los pocos ms y deja la tabla sin ninguna pista de que sigue a la derecha. Al
       declarar ::-webkit-scrollbar el navegador pinta la clásica, que ocupa sitio y se ve. */
    .scroll { overflow-x: auto; }
    .scroll::-webkit-scrollbar { height: 10px; }
    .scroll::-webkit-scrollbar-track { background: transparent; }
    .scroll::-webkit-scrollbar-thumb { background: color-mix(in srgb, var(--color) 25%, transparent); border-radius: 6px; }
    .scroll::-webkit-scrollbar-thumb:hover { background: color-mix(in srgb, var(--color) 40%, transparent); }
    /* #120 - The grid floor is the SUM OF THE COLUMN MINIMUMS (min-content), not its maximum
       size. With max-content the grid sizes itself to what the widest column asks for and, in
       doing so, every 1fr track ends up as wide AS THAT ONE: at 834px each column measured
       148.86px for content asking between 10px (a "4") and 100px ("Familia Perez"). The table
       always overflowed and the pinned actions column sat on top of Pax and Estado. With
       min-content the grid fits its container as long as the minimums fit, and 1fr shares out the
       leftover space; horizontal scroll shows up only when not even the minimums fit. */
    .grid { min-width: min-content; font-size: 14px; }
    .grow { display: grid; align-items: center; gap: 0.5rem; padding: 0 1rem; }
    .ghead { position: sticky; top: 0; z-index: 2; border-bottom: 1px solid var(--border-color);
      background: var(--header-background); padding-top: 0.55rem; padding-bottom: 0.55rem; }
    .gcell { display: flex; align-items: center; min-width: 0; }
    .gcell > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .gcell.right { justify-content: flex-end; text-align: right; }
    .gcell.center { justify-content: center; text-align: center; }
    /* #67 - PINNED ACTIONS COLUMN. When the grid overflows (since #120 only when not even the
       column minimums fit; before that it happened with six columns and room to spare) the button
       that opens the record went off screen: at 1440px it sat 335px past the edge with nothing to
       give it away. It stays stuck to the right edge, like Zendesk/Freshdesk/Shopify. With
       background:inherit it takes the row background (which is opaque for this very reason), so it
       keeps hover and selection without anything showing through. */
    .gcell.actions-col { position: sticky; right: 0; z-index: 1; background: inherit;
      margin-right: -1rem; padding-right: 1rem; }
    /* La sombra solo aparece cuando de verdad hay algo escondido a la izquierda (clase x-overflow);
       si la tabla cabe entera no se pinta nada. */
    .scroll.x-overflow .gcell.actions-col { box-shadow: -10px 0 10px -10px color-mix(in srgb, var(--color) 45%, transparent); }
    /* #120 - The pinned header has to be OPAQUE. background:inherit took --header-background,
       which is a 4% alpha TINT (measured rgba(24,24,27,0.04)): when the grid overflows the
       "Acciones" header went see-through and "PAX" and "ESTADO" could be read through it - the
       "PAXCIONESTAD" of the issue. It now sits on the opaque table background with the tint laid
       back on top, the same way .grow-data:hover does. */
    .ghead .gcell.actions-col { z-index: 3;
      background: linear-gradient(var(--header-background), var(--header-background)), var(--background); }
    .gh { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-muted); }
    .gh.sortable { cursor: pointer; user-select: none; white-space: nowrap; transition: background-color var(--ok-transition, 150ms ease), color var(--ok-transition, 150ms ease), box-shadow var(--ok-transition, 150ms ease), transform 120ms ease; }
    @media (hover: hover) {
      .gh.sortable:hover { color: var(--color); }
    }
    /* Caret de orden (3 estados, icono Ionic): neutral atenuado / activo en color primario. */
    .caret { display: inline-flex; align-items: center; margin-left: 0.25rem; flex: 0 0 auto; font-size: 13px; opacity: 0.3; }
    .caret.on { opacity: 1; color: var(--primary); }
    .grow-data { background: var(--background); border-bottom: 1px solid var(--border-color-soft); padding-top: 0.6rem; padding-bottom: 0.6rem; transition: background-color var(--ok-transition, 150ms ease), color var(--ok-transition, 150ms ease), box-shadow var(--ok-transition, 150ms ease), transform 120ms ease; }
    .grow-data:last-child { border-bottom: 0; }
    @media (hover: hover) {
      .grow-data:hover { background: linear-gradient(var(--row-hover), var(--row-hover)), var(--background); }
    }
    .grow-data:active { transform: scale(0.995); }
    .grow-data.selected { background: linear-gradient(color-mix(in srgb, var(--primary) 10%, transparent), color-mix(in srgb, var(--primary) 10%, transparent)), var(--background); }
    /* #67 — Fila clicable (opt-in row-clickable): es lo primero que intenta el usuario y lo que
       hacen Odoo, Jira SM, Shopify o Square en sus listados. */
    .grow-data.clickable { cursor: pointer; }
    .grow-data.clickable:focus-visible { outline: 2px solid var(--primary); outline-offset: -2px; }
    .selcb { display: flex; align-items: center; justify-content: center; }
    .filters-grow { padding-top: 0.4rem; padding-bottom: 0.6rem; }
    .filters-grow input, .filters-grow select { width: 100%; box-sizing: border-box; font: inherit; font-size: 13px; padding: 0.3rem 0.4rem; border: 1px solid var(--border-color); border-radius: 6px; background: var(--background); color: var(--color); }
    .range { display: flex; gap: 0.25rem; }

    /* ── Vista tarjetas ──────────────────────────────────────────────────────────────────── */
    /* Cada tarjeta mide SU contenido (no se estira al alto de la fila ni del contenedor):
       - grid-auto-rows: max-content → cada fila implícita = alto de su contenido. CLAVE: sin esto,
         en modo fill (grid de alto fijo + align-content:start) cuando las tarjetas no caben el
         navegador encoge los tracks de fila y las tarjetas se solapan.
       - align-content: start → empaqueta las filas arriba (no reparte el hueco sobrante estirando).
       - align-items: start → en una fila multi-columna cada tarjeta mide su propio contenido.
       En modo fill el grid es flex-child con overflow:auto → cuando las tarjetas no caben aparece el
       scroll DENTRO de la tabla (no crece hacia fuera). */
    .cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 0.75rem; padding: 1rem; grid-auto-rows: max-content; align-content: start; align-items: start; }
    /* Tarjeta = ion-card NATIVO de Ionic: su fondo, radio, elevación y padding son los de Ionic y NO
       se sobrescriben. Aquí solo se ajusta lo que el contexto de rejilla exige (margin) y los huecos
       que Ionic no trae (cabecera en fila, filas clave-valor, barra de acciones, resalte de selección). */
    ion-card.rcard { margin: 0; } /* la rejilla aporta el gap → sin esto el margin por defecto de ion-card lo duplica */
    ion-card.rcard.selected { outline: 2px solid var(--primary); outline-offset: -2px; }
    /* #74 — Tarjeta clicable (opt-in row-clickable): la mitad de #67 que faltaba. La vista de
       tarjetas es la que la tabla elige SOLA en móvil, así que sin esto el registro no se podía
       abrir desde un teléfono (medido con combos 0.1.4: 0 rowClick a 390px). */
    ion-card.rcard.clickable { cursor: pointer; }
    ion-card.rcard.clickable:focus-visible { outline: 2px solid var(--primary); outline-offset: -2px; }
    @media (prefers-reduced-motion: reduce) {
      .gh.sortable:hover, .gh.sortable:active,
      .grow-data:hover, .grow-data:active { transform: none; }
    }
    /* Header: ion-card-header as a single row (icon + title + checkbox), keeping Ionic's padding.
       #79 — flex-direction/flex-wrap are SPELLED OUT on purpose: in ios mode (the mode the Hub
       shell pins, ADR-0143) Ionic's own host CSS gives ion-card-header a column direction, so a
       rule that only sets display:flex inherits it and the three children stack on three lines.
       Under md the same rule looked right, which is why it shipped. */
    ion-card-header.rcard-head { display: flex; flex-direction: row; flex-wrap: nowrap; align-items: center; gap: 0.5rem; }
    .rcard-head .rc-icon { display: inline-flex; color: var(--primary); }
    .rcard-head .rc-title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; }
    /* Cuerpo: ion-card-content (padding Ionic por defecto) con las filas clave-valor apiladas. */
    ion-card-content.rcard-body { display: flex; flex-direction: column; gap: 0.4rem; }
    .rrow { display: flex; justify-content: space-between; gap: 0.5rem; font-size: 13px; }
    .rrow .rk { color: var(--color-muted); }
    .rrow .rv { font-weight: 500; text-align: right; color: var(--color); }
    /* Barra de acciones (Ionic no trae "card actions"): pie alineado a la derecha, fondo transparente. */
    .ractions { display: flex; justify-content: flex-end; gap: 0.25rem; padding: 0 0.5rem 0.5rem; }
    /* ERPlora/appointments#154 - a card's action row must NEVER clip.
       The assumption was that they always fit across the card. With the eight actions an
       appointment carries they do not: on a 411dp phone the card leaves 363px and the buttons ask
       for 380px (8 x 44px of tap floor + 7 gaps of 4px). Without wrapping, justify-content:
       flex-end takes that difference off the START side, so the FIRST button - Cobrar - hung off
       the left edge of the card, clipped, with no scrollbar and nothing to say it was there.
       The wrap is scoped to the card on purpose: the LIST view's row is measured by its
       scrollWidth to pin the column track (#121), and a row that wraps changes width with the
       track it is measured against, which is the loop that measure avoids. */
    .ractions .actions { flex-wrap: wrap; }

    /* ── Estado vacío ────────────────────────────────────────────────────────────────────── */
    .empty { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.75rem; padding: 3.5rem 1rem; text-align: center; color: var(--color-muted); }
    .empty .empty-ic { display: grid; place-items: center; width: 3.25rem; height: 3.25rem; border-radius: 999px; background: var(--header-background); font-size: 26px; }

    .actions { display: flex; gap: 0.25rem; justify-content: flex-end; }
    /* #121 - The buttons NEVER shrink. Their track is pinned to the width measured here
       (the scrollWidth of .actions); if they could shrink, a narrow track would shrink the
       measurement, which would shrink the track again. flex: 0 0 auto is what makes the
       measurement a property of the CONTENT instead of a property of the current layout. */
    .actions ion-button { flex: 0 0 auto; }
    /* #122 - Header of the actions column while the buttons are folded into the menu. "ACCIONES"
       measures 62.83px and the folded track is 44px: painted, it spills out of its own cell and
       over "Estado" - the very thing the issue is about. The column keeps its name for assistive
       tech and paints nothing. */
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden;
      clip-path: inset(50%); white-space: nowrap; border: 0; }
    /* Las acciones de fila son icon-only y de tamaño small en escritorio. En tablet/móvil se
     * amplía el host completo (no solo el icono) para que el área táctil alcance 44×44 px. */
    @media (pointer: coarse), (max-width: 834px) {
      .actions ion-button { min-width: 44px; min-height: 44px; margin: 0; }
      .toolbtn { width: 44px; height: 44px; }
      .add-btn { min-height: 44px; }
      .pager .nav ion-button { min-width: 44px; min-height: 44px; margin: 0; }
    }
    /* Spinner de acción en curso (loading): contenido dentro del ion-button small (Ionic lo fija
     * a 28px en el :host, por eso width/height y no font-size). Cubre tabla y tarjetas: los
     * botones de fila siempre van dentro de .actions. */
    .actions ion-spinner { width: 18px; height: 18px; }

    /* ── Pie: contador + paginación ──────────────────────────────────────────────────────── */
    .pager { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; padding: 0.55rem 1rem; border-top: 1px solid var(--border-color); background: var(--header-background); font-size: 12.5px; color: var(--color-muted); }
    .pager .left { display: flex; align-items: center; gap: 0.6rem; }
    .pager .strong { font-weight: 600; color: var(--color); }
    .psize { font: inherit; font-size: 12.5px; padding: 0.2rem 0.35rem; border: 1px solid var(--border-color); border-radius: 6px; background: var(--background); color: var(--color); }
    .pager .nav { display: flex; align-items: center; gap: 0.2rem; }
    /* #78 — Pie en MÓVIL: un solo control «Cargar más» en lugar del pager numerado (Shopify
       IndexTable, Fresha, Square y Material hacen lo mismo: nadie pinta botones de página en un
       teléfono). Sin atributo fill: el sólido por defecto de Ionic es el único que pinta caja en
       modo ios (outfitkit#82 / ADR-0143). Los 44px son el área táctil mínima. */
    .pager .load-more { min-height: 44px; margin: 0; --padding-start: 1rem; --padding-end: 1rem; font-size: 13px; }
    .pager .nav .pp { font-weight: 600; color: var(--color); padding: 0 0.25rem; }
    /* Pager numerado: botón por página + «…» en los saltos (look del Hub). */
    /* #92 — min-width/height at 44px so a numbered page button matches the prev/next ion-button's
       own 44px tap target (line above): before this they were visibly smaller than their neighbors. */
    .pnum { min-width: var(--ok-tap-min, 44px); height: var(--ok-tap-min, 44px); padding: 0 0.4rem; border: 1px solid transparent; border-radius: 8px; background: none; font: inherit; font-size: 12.5px; font-weight: 600; color: var(--color); cursor: pointer; transition: background 0.12s, border-color 0.12s; }
    .pnum:hover { background: var(--row-hover); }
    .pnum.on { background: color-mix(in srgb, var(--primary) 14%, transparent); color: var(--primary); border-color: color-mix(in srgb, var(--primary) 40%, transparent); }
    .pgap { padding: 0 0.15rem; color: var(--color-muted); }
    ion-button { --box-shadow: none; }
  `;
  }
  static {
    this.MOBILE_BREAKPOINT = 640;
  }
  connectedCallback() {
    super.connectedCallback();
    if (typeof window !== "undefined") {
      window.addEventListener("erplora:locale-changed", this.onLocaleChanged);
      window.addEventListener("resize", this.onWindowResize);
    }
    if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
      this.mq = window.matchMedia(`(max-width: ${_OkDataTable2.MOBILE_BREAKPOINT}px)`);
      this.isMobile = this.mq.matches;
      const handler = (e5) => {
        const matches = "matches" in e5 ? e5.matches : this.mq?.matches ?? false;
        if (this.isMobile === matches) return;
        this.isMobile = matches;
        if (matches && this.cardViewEnabled) this.viewMode = "cards";
        else if (!matches && this.viewMode === "cards") this.viewMode = "table";
      };
      this.mq.addEventListener("change", handler);
      this._mqHandler = handler;
    }
  }
  /** #67 — Recalcula si la vista lista desborda a lo ancho (`scrollWidth > clientWidth`).
   *
   * Se mide después de renderizar, que es cuando el navegador ya conoce los anchos, y solo se
   * escribe el estado si CAMBIA: asignarlo siempre reprogramaría un render en bucle. */
  measureXOverflow() {
    const scroll = this.renderRoot?.querySelector?.(".scroll");
    const overflow = !!scroll && scroll.scrollWidth > scroll.clientWidth;
    if (this.xOverflow !== overflow) this.xOverflow = overflow;
  }
  /** #121 — Ancho natural de los botones de acción de una fila, para clavar su pista en px.
   *
   * Se lee del `scrollWidth` de `.actions`, que es el ancho de SU CONTENIDO: como los botones
   * llevan `flex: 0 0 auto` nunca se encogen, así que la medida no depende de lo ancha que sea la
   * pista en ese momento. Eso es lo que la hace estable: clavar la pista al ancho natural no
   * cambia el ancho natural, así que la siguiente medida sale igual y no hay bucle. */
  measureActionsTrack() {
    if (!this.actions.length) {
      if (this.actionsTrackPx !== 0) this.actionsTrackPx = 0;
      return;
    }
    const boxes = this.renderRoot?.querySelectorAll?.(".grow-data .gcell.actions-col .actions") ?? [];
    let width = 0;
    for (const el of boxes) width = Math.max(width, Math.ceil(el.scrollWidth));
    if (width > 0 && width !== this.actionsTrackPx) this.actionsTrackPx = width;
  }
  /** #122 — Decide si los botones de acción de la fila caben o se pliegan en el menú «⋮».
   *  El criterio y la garantía de que no oscila viven en `decideRowActionsFit`. */
  measureRowActionsFit() {
    const scroll = this.renderRoot?.querySelector?.(".scroll");
    if (!scroll) return;
    const next = decideRowActionsFit({
      containerWidth: scroll.clientWidth,
      contentWidth: scroll.scrollWidth,
      collapsed: this.rowActionsCollapsed,
      decidedAtWidth: this.fitDecidedAtWidth
    });
    this.fitDecidedAtWidth = next.decidedAtWidth;
    if (this.rowActionsCollapsed !== next.collapsed) this.rowActionsCollapsed = next.collapsed;
  }
  /** Engancha el observador al contenedor de scroll del render actual (cambia entre vistas). */
  observeXOverflow() {
    if (typeof ResizeObserver === "undefined") return;
    const scroll = this.renderRoot?.querySelector?.(".scroll");
    if (!scroll) return;
    this.xObserver ??= new ResizeObserver(() => {
      this.measureXOverflow();
      this.measureActionsTrack();
      this.measureRowActionsFit();
    });
    this.xObserver.disconnect();
    this.xObserver.observe(scroll);
    const grid = scroll.querySelector(".grid");
    if (grid) this.xObserver.observe(grid);
  }
  updated(changed) {
    this.observeXOverflow();
    this.measureXOverflow();
    if (changed.has("columns") || changed.has("actions") || changed.has("hiddenKeys") || changed.has("selectable")) {
      this.fitDecidedAtWidth = -1;
    }
    this.measureActionsTrack();
    this.measureRowActionsFit();
    if (changed.has("panel")) this.syncSheetTop();
  }
  /** #75 — Where the mobile sheet starts. `position: fixed; inset: 0` painted it from y=0 and the
   *  app's `ion-header` (its own stacking context, above the content) covered the sheet's title and
   *  its only Close button — measured at 390×844 in the Appointments parity page. CSS inside a
   *  shadow root cannot know where the content area begins, so on open the table measures the
   *  closest `ion-content` (walking through shadow hosts) and hands the offset over as a custom
   *  property; on close it is removed. Without an `ion-content` around, the sheet keeps y=0. */
  syncSheetTop() {
    if (this.panel === "none") {
      this.style.removeProperty("--ok-sheet-top");
      return;
    }
    let node = this;
    let content = null;
    while (node && !content) {
      const parent = node.parentNode ?? node.getRootNode?.()?.host ?? null;
      if (parent && parent.nodeType === Node.ELEMENT_NODE && parent.tagName === "ION-CONTENT") content = parent;
      node = parent === node ? null : parent;
    }
    const top = content ? Math.max(0, Math.round(content.getBoundingClientRect().top)) : 0;
    this.style.setProperty("--ok-sheet-top", `${top}px`);
  }
  disconnectedCallback() {
    if (typeof window !== "undefined") {
      window.removeEventListener("erplora:locale-changed", this.onLocaleChanged);
      window.removeEventListener("resize", this.onWindowResize);
    }
    this.xObserver?.disconnect();
    this.xObserver = void 0;
    if (this.mq) {
      const handler = this._mqHandler;
      if (handler) this.mq.removeEventListener("change", handler);
      this.mq = void 0;
    }
    super.disconnectedCallback();
  }
  // ── i18n: idioma del documento ← overrides explícitos de `.labels` ─────────────────────────
  get t() {
    const lang = typeof document === "undefined" ? "en" : document.documentElement.lang.toLowerCase();
    return { ...lang.startsWith("es") ? ES_LABELS : DEFAULT_LABELS, ...this.labels };
  }
  /** Placeholder efectivo del buscador (prop explícita → label i18n → default inglés). */
  get effSearchPlaceholder() {
    return this.searchPlaceholder ?? this.t.search;
  }
  /** Mensaje efectivo de estado vacío (prop explícita → label i18n → default inglés). */
  get effEmptyMessage() {
    return this.emptyMessage ?? this.t.empty;
  }
  /** #171 — Effective "no matches" message (explicit prop → i18n label → English default). */
  get effNoMatchesMessage() {
    return this.noMatchesMessage ?? this.t.noMatches;
  }
  // ── Resolución de alias (compat + documentados) ──────────────────────────────────────────
  get effPageSizes() {
    return this.pageSizes ?? this.pageSizeOptions;
  }
  get effColumnPicker() {
    return this.columnPicker || this.columnSelector;
  }
  get effExport() {
    return this.csv || this.exportable;
  }
  get effImport() {
    return this.csv || this.importable;
  }
  /** ¿Está habilitado el conmutador de vista lista/tarjetas? */
  get viewToggle() {
    if (Array.isArray(this.views)) return this.views.length > 1;
    return this.views === true;
  }
  /** ¿Está disponible la vista tarjetas? (presente en `views` o `views === true`). */
  get cardViewEnabled() {
    if (Array.isArray(this.views)) return this.views.some((v3) => v3 === "cards" || v3 === "card");
    return this.views === true;
  }
  /** Columnas actualmente visibles (respeta el column chooser). */
  get visibleColumns() {
    return this.hiddenKeys.size ? this.columns.filter((c5) => !this.hiddenKeys.has(c5.key)) : this.columns;
  }
  setVisibleColumns(keys) {
    const visible = new Set(keys);
    this.hiddenKeys = new Set(this.columns.map((c5) => c5.key).filter((k2) => !visible.has(k2)));
    this.emit("columnsChange", { visible: keys });
  }
  // ── Selección ─────────────────────────────────────────────────────────────────────────────
  keyOf(row) {
    if (typeof this.rowKey === "function") return String(this.rowKey(row) ?? "");
    if (typeof this.rowKey === "string") return String(row[this.rowKey] ?? "");
    return String(row[this.rowKeyField] ?? "");
  }
  /** #143 — `<prefix>-<suffix>`, or `nothing` (= the attribute is not painted) when the host gave
   *  no prefix. A blank prefix counts as absent: `" "` would leave dangling `-add` hooks, identical
   *  on every table of the screen, which is exactly what the prefix prevents. */
  tid(suffix) {
    const prefix = this.testid?.trim();
    return prefix ? `${prefix}-${suffix}` : A;
  }
  get selection() {
    return this.selectedKeys ?? this.internalSelection;
  }
  setSelection(next) {
    if (!this.selectedKeys) this.internalSelection = next;
    this.emit("selectionChange", { keys: [...next] });
    this.requestUpdate();
  }
  toggleRow(key) {
    const next = new Set(this.selection);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    this.setSelection(next);
  }
  toggleAll(visible) {
    const keys = visible.map((r6) => this.keyOf(r6));
    const allOn = keys.length > 0 && keys.every((k2) => this.selection.has(k2));
    const next = new Set(this.selection);
    if (allOn) keys.forEach((k2) => next.delete(k2));
    else keys.forEach((k2) => next.add(k2));
    this.setSelection(next);
  }
  // ── CSV ─────────────────────────────────────────────────────────────────────────────────────
  csvEscape(v3) {
    const s5 = v3 === null || v3 === void 0 ? "" : String(v3);
    return /[",\n\r]/.test(s5) ? `"${s5.replace(/"/g, '""')}"` : s5;
  }
  /** Exporta las filas a CSV (cabeceras = column.key). Si no hay filas, exporta solo la estructura. */
  exportCsv() {
    const cols = this.columns;
    const head = cols.map((c5) => this.csvEscape(c5.key)).join(",");
    const lines = this.rows.map((r6) => cols.map((c5) => this.csvEscape(r6[c5.key])).join(","));
    const csv = [head, ...lines].join("\r\n");
    const blob = new Blob([CSV_BOM + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a3 = document.createElement("a");
    a3.href = url;
    a3.download = this.csvName;
    a3.click();
    URL.revokeObjectURL(url);
    const count = this.rows.length;
    this.emit("csvExport", { rows: count, count });
    this.emit("export", { rows: count, count });
  }
  parseCsv(text3) {
    const out = [];
    let row = [];
    let field = "";
    let q = false;
    for (let i7 = 0; i7 < text3.length; i7++) {
      const c5 = text3[i7];
      if (q) {
        if (c5 === '"') {
          if (text3[i7 + 1] === '"') {
            field += '"';
            i7++;
          } else q = false;
        } else field += c5;
      } else if (c5 === '"') q = true;
      else if (c5 === ",") {
        row.push(field);
        field = "";
      } else if (c5 === "\n" || c5 === "\r") {
        if (c5 === "\r" && text3[i7 + 1] === "\n") i7++;
        row.push(field);
        field = "";
        if (row.length > 1 || row[0] !== "") out.push(row);
        row = [];
      } else field += c5;
    }
    if (field !== "" || row.length) {
      row.push(field);
      out.push(row);
    }
    const headers = out.shift() ?? [];
    const rows = out.map((r6) => Object.fromEntries(headers.map((h4, i7) => [h4, r6[i7] ?? ""])));
    return { headers, rows };
  }
  async onImportFile(ev) {
    const input = ev.target;
    const file = input.files?.[0];
    if (!file) return;
    const text3 = decodeCsvBuffer(await file.arrayBuffer());
    const { headers, rows } = this.parseCsv(text3);
    this.emit("csvImport", { headers, rows, count: rows.length });
    this.emit("import", { headers, rows, count: rows.length });
    input.value = "";
  }
  toggle(p4) {
    if (p4 === "filters" && this.panel !== "filters") {
      this.filterDraft = this.cloneFilters(this.clientFilters);
    }
    this.panel = this.panel === p4 ? "none" : p4;
  }
  // ── Filtros en memoria (modo cliente): borrador → aplicar. ───────────────────────────────────
  cloneFilters(src) {
    const out = {};
    for (const [k2, f3] of Object.entries(src)) {
      out[k2] = { values: f3.values ? new Set(f3.values) : void 0, from: f3.from, to: f3.to };
    }
    return out;
  }
  // Fija el conjunto de valores seleccionados de una columna (multi-select del drawer = ion-select).
  setFilterValues(key, values) {
    const next = this.cloneFilters(this.filterDraft);
    const clean = (values ?? []).filter((v3) => v3 != null && v3 !== "");
    if (clean.length) next[key] = { ...next[key], values: new Set(clean) };
    else next[key] = { ...next[key], values: void 0 };
    this.filterDraft = next;
  }
  setFilterRange(key, edge, value) {
    const next = this.cloneFilters(this.filterDraft);
    next[key] = { ...next[key], [edge]: value };
    this.filterDraft = next;
  }
  applyFilters() {
    const clean = {};
    for (const [k2, f3] of Object.entries(this.filterDraft)) {
      if (f3.values && f3.values.size > 0 || f3.from || f3.to) clean[k2] = f3;
    }
    this.clientFilters = clean;
    this.clientPage = 0;
    this.mobileShown = 0;
    this.panel = "none";
    this.emit("filterChange", { filters: this.serializeFilters(clean) });
  }
  clearFilters() {
    this.filterDraft = {};
  }
  /** #171 — "Show all" under the no-matches state: drops the search AND the column filters, so
   *  every row is back in one tap. Consumers listening to `filterChange` hear the reset. */
  resetSearchAndFilters() {
    const hadFilters = Object.keys(this.clientFilters).length > 0;
    this.q = "";
    this.clientFilters = {};
    this.filterDraft = {};
    this.clientPage = 0;
    this.mobileShown = 0;
    if (hadFilters) this.emit("filterChange", { filters: {} });
  }
  serializeFilters(src) {
    const out = {};
    for (const [k2, f3] of Object.entries(src)) {
      if (f3.values && f3.values.size > 0) out[k2] = [...f3.values];
      else if (f3.from || f3.to) out[k2] = { from: f3.from ?? "", to: f3.to ?? "" };
    }
    return out;
  }
  /** Abre el panel lateral (API pública para el módulo, p.ej. "editar" abre el form pre-rellenado). */
  open(panel = "create") {
    this.panel = panel;
  }
  /** Cierra el panel lateral. */
  close() {
    this.panel = "none";
  }
  emit(type, detail) {
    this.dispatchEvent(new CustomEvent(type, { detail, bubbles: true, composed: true }));
  }
  get hasSearch() {
    return this.searchable || this.searchKeys.length > 0;
  }
  /** Columnas filtrables (con control en el panel de filtros). En cliente y en servidor. */
  get filterColumns() {
    return this.columns.filter((c5) => c5.filterable);
  }
  /** ¿Hay que mostrar el botón de Filtros? (cualquier columna filtrable). */
  get hasFilterRow() {
    return this.filterColumns.length > 0;
  }
  /** Nº de filtros activos → badge del botón Filtros. En servidor cuenta `filterValues` (#106): sin
   *  esto el embudo no daba NINGUNA señal de que la lista venía acotada. */
  get activeFilterCount() {
    if (this.serverSide) {
      return Object.keys(this.serverFilters).filter((k2) => this.serverFilterState(k2) !== void 0).length;
    }
    return Object.values(this.clientFilters).filter(
      (f3) => f3.values && f3.values.size > 0 || f3.from || f3.to
    ).length;
  }
  // ── Estado de filtro VISIBLE (#106) ──────────────────────────────────────────────────────────
  /** Traduce un valor de `filterValues` (la forma que emite `filterChange`) a la forma interna que
   *  usan los `render*Filter`. `undefined` = ese filtro no está puesto. */
  serverFilterState(key) {
    const raw = this.serverFilters[key];
    if (raw === void 0 || raw === null || raw === "") return void 0;
    if (Array.isArray(raw)) {
      const values = raw.filter((v3) => v3 !== null && v3 !== void 0 && v3 !== "").map((v3) => String(v3));
      return values.length ? { values: new Set(values) } : void 0;
    }
    if (typeof raw === "object") {
      const range = raw;
      const from = range.from === null || range.from === void 0 || range.from === "" ? void 0 : String(range.from);
      const to = range.to === null || range.to === void 0 || range.to === "" ? void 0 : String(range.to);
      return from !== void 0 || to !== void 0 ? { from, to } : void 0;
    }
    return { values: /* @__PURE__ */ new Set([String(raw)]) };
  }
  /** Estado de filtro efectivo de una columna: servidor → `filterValues`/espejo; cliente → memoria. */
  filterStateOf(key) {
    return this.serverSide ? this.serverFilterState(key) : this.clientFilters[key];
  }
  /** Fija (o borra) el valor visible de un filtro en el espejo de servidor. */
  setServerFilter(key, value) {
    const next = { ...this.serverFilters };
    const empty = value === void 0 || value === null || value === "" || Array.isArray(value) && value.length === 0;
    if (empty) delete next[key];
    else next[key] = value;
    this.serverFilters = next;
  }
  /** Fija UN extremo de un rango en el espejo. Los dos extremos viajan en eventos SEPARADOS
   *  (`{from}` y luego `{to}`), así que aquí se MEZCLA: reemplazar borraría el otro extremo. */
  setServerRangeEdge(key, edge, value) {
    const prev = this.serverFilters[key];
    const base = prev && typeof prev === "object" && !Array.isArray(prev) ? { ...prev } : {};
    base[edge] = value;
    const alive = (v3) => v3 !== void 0 && v3 !== null && v3 !== "";
    this.setServerFilter(key, alive(base.from) || alive(base.to) ? base : void 0);
  }
  /** Valor crudo de una columna para ordenar/filtrar (usa format si lo hay, si no row[key]). */
  rawValue(col, row) {
    if (col.format) return col.format(row);
    return row[col.key];
  }
  /** Valores distintos de una columna (para los chips del filtro multi-select). */
  distinctValues(col) {
    const set = /* @__PURE__ */ new Set();
    for (const row of this.rows) {
      const v3 = this.rawValue(col, row);
      if (v3 != null && v3 !== "") set.add(String(v3));
    }
    return [...set].sort((a3, b3) => a3.localeCompare(b3));
  }
  /** Filas tras buscar + filtrar + ordenar EN MEMORIA (solo modo cliente). */
  get clientFiltered() {
    let result = this.rows;
    const needle = this.q.trim().toLowerCase();
    if (needle && this.searchKeys.length) {
      result = result.filter(
        (r6) => this.searchKeys.some((k2) => String(r6[k2] ?? "").toLowerCase().includes(needle))
      );
    }
    const fkeys = Object.keys(this.clientFilters);
    if (fkeys.length) {
      result = result.filter(
        (row) => fkeys.every((key) => {
          const f3 = this.clientFilters[key];
          const col = this.columns.find((c5) => c5.key === key);
          if (!col) return true;
          if (f3.values && f3.values.size > 0) {
            return f3.values.has(String(this.rawValue(col, row) ?? ""));
          }
          if (f3.from || f3.to) {
            const raw = this.rawValue(col, row);
            const t5 = raw == null ? NaN : new Date(raw).getTime();
            const from = f3.from ? new Date(f3.from).getTime() : -Infinity;
            const to = f3.to ? new Date(f3.to).getTime() + 864e5 - 1 : Infinity;
            return !Number.isNaN(t5) && t5 >= from && t5 <= to;
          }
          return true;
        })
      );
    }
    if (this.clientSort) {
      const col = this.columns.find((c5) => c5.key === this.clientSort);
      if (col) {
        const dir = this.clientSortDir === "asc" ? 1 : -1;
        result = [...result].sort((a3, b3) => {
          const va = this.rawValue(col, a3);
          const vb = this.rawValue(col, b3);
          if (va == null) return 1;
          if (vb == null) return -1;
          if (va < vb) return -1 * dir;
          if (va > vb) return 1 * dir;
          return 0;
        });
      }
    }
    return result;
  }
  cell(col, row) {
    if (col.format) return col.format(row);
    const v3 = row[col.key];
    return v3 === null || v3 === void 0 ? "" : String(v3);
  }
  /** ¿Es ordenable la columna? Servidor: opt-in (`sortable`). Cliente: por defecto SÍ (como el Hub),
   *  salvo `sortable: false` explícito. */
  isSortable(col) {
    return this.serverSide ? !!col.sortable : col.sortable !== false;
  }
  onHeaderClick(col) {
    if (!this.isSortable(col)) return;
    if (this.serverSide) {
      const dir = this.sort === col.key && this.sortDir === "asc" ? "desc" : "asc";
      this.emit("sortChange", { sort: col.key, dir });
      return;
    }
    this.mobileShown = 0;
    if (this.clientSort === col.key) {
      this.clientSortDir = this.clientSortDir === "asc" ? "desc" : "asc";
    } else {
      this.clientSort = col.key;
      this.clientSortDir = "asc";
    }
  }
  onFilterInput(col, ev) {
    const value = ev.target.value ?? "";
    this.setServerFilter(col.key, value);
    this.emit("filterChange", { col: col.key, value });
  }
  onRangeInput(col, edge, ev) {
    const raw = ev.target.value ?? "";
    const v3 = raw === "" ? "" : Number(raw);
    this.setServerRangeEdge(col.key, edge, v3);
    this.emit("filterChange", { col: col.key, value: { [edge]: v3 } });
  }
  onDateRangeInput(col, edge, ev) {
    const v3 = ev.target.value ?? "";
    this.setServerRangeEdge(col.key, edge, v3);
    this.emit("filterChange", { col: col.key, value: { [edge]: v3 } });
  }
  // ── Filtros EN LÍNEA (toolbar) ────────────────────────────────────────────────────────────
  // En modo cliente escriben directamente `clientFilters` (filtran en memoria); en servidor solo
  // emiten `filterChange`. Reutilizan la misma forma de filtro que el drawer (values / from / to).
  setClientFilter(key, patch) {
    const next = { ...this.clientFilters };
    const merged = { ...next[key], ...patch };
    const empty = (!merged.values || merged.values.size === 0) && !merged.from && !merged.to;
    if (empty) delete next[key];
    else next[key] = merged;
    this.clientFilters = next;
    this.clientPage = 0;
    this.mobileShown = 0;
  }
  // ion-select (select/multiselect) del panel de filtros (renderFilterControl). En servidor emite
  // `filterChange`; en cliente escribe `clientFilters` (multiselect ⇒ filtra por inclusión).
  onFilterSelect(col, value, multi) {
    if (this.serverSide) {
      const next = value ?? (multi ? [] : "");
      this.setServerFilter(col.key, next);
      this.emit("filterChange", { col: col.key, value: next });
      return;
    }
    if (multi) {
      const arr = Array.isArray(value) ? value.map((v3) => String(v3)) : value != null && value !== "" ? [String(value)] : [];
      this.setClientFilter(col.key, { values: arr.length ? new Set(arr) : void 0 });
    } else {
      const v3 = String(value ?? "");
      this.setClientFilter(col.key, { values: v3 ? /* @__PURE__ */ new Set([v3]) : void 0 });
    }
  }
  onInlineRange(col, edge, ev) {
    const v3 = ev.target.value ?? "";
    if (this.serverSide) {
      this.setServerRangeEdge(col.key, edge, v3);
      this.emit("filterChange", { col: col.key, value: { [edge]: v3 } });
      return;
    }
    this.setClientFilter(col.key, { [edge]: v3 || void 0 });
  }
  // Menú overflow: ancla el popover al botón vía el evento de click (compatible con Shadow DOM).
  openMenu(ev) {
    this.menuEv = ev;
    this.menuOpen = true;
  }
  /** #122 — Abre el menú «⋮» de UNA fila. Un solo popover para toda la tabla (uno por fila serían
   *  tantos como filas), anclado por evento porque `trigger` no resuelve dentro de Shadow DOM. */
  openRowMenu(ev, row) {
    ev.stopPropagation();
    this.rowMenuEv = ev;
    this.rowMenuRow = row;
    this.rowMenuOpen = true;
  }
  /** #122 — Las mismas acciones de la fila, como lista. Respeta `disabled`/`loading` por fila: una
   *  acción que no se puede pulsar en su botón tampoco se puede pulsar aquí. */
  renderRowMenu() {
    const row = this.rowMenuRow;
    if (!this.actions.length || !row) return A;
    const actions = this.visibleActions(row);
    const key = this.keyOf(row);
    return b2`
      <ion-popover
        class="row-menu"
        .isOpen=${this.rowMenuOpen}
        .event=${this.rowMenuEv}
        dismiss-on-select="true"
        @didDismiss=${() => this.rowMenuOpen = false}
      >
        <ion-content>
          <ion-list lines="none">
            ${actions.map((a3) => {
      const disabled = a3.loading?.(row) === true || a3.disabled?.(row) === true;
      const label = typeof a3.label === "function" ? a3.label(row) : a3.label;
      return b2`
                <!-- #143 — The action is named the SAME collapsed or not, so one spec works at any
                     width. It carries the hook only while the direct buttons are NOT there: the
                     popover survives its dismissal («rowMenuRow» is not cleared), and if the table
                     widened again there would be TWO elements with the hook and «getByTestId»
                     would pick one at random. -->
                <ion-item
                  button
                  data-testid=${this.rowActionsCollapsed ? this.tid(`row-${key}-${a3.id}`) : A}
                  ?disabled=${disabled}
                  aria-disabled=${disabled ? "true" : A}
                  .detail=${false}
                  @click=${() => {
        if (disabled) return;
        this.rowMenuOpen = false;
        this.emit("rowAction", { actionId: a3.id, row });
      }}
                >
                  ${a3.icon ? b2`<ion-icon slot="start" .icon=${okIcon(a3.icon)} style=${ionTone(a3.color, "text") ?? A}></ion-icon>` : A}
                  <ion-label style=${ionTone(a3.color, "text") ?? A}>${label}</ion-label>
                </ion-item>
              `;
    })}
          </ion-list>
        </ion-content>
      </ion-popover>
    `;
  }
  // Aplica la vista inicial declarada (`default-view`) una sola vez, tras el primer render. Es la
  // forma robusta de arrancar en tarjetas sin depender de fijar `viewMode` por referencia (que
  // falla si la tabla monta detrás de un `v-if`/loading y el ref aún es null).
  firstUpdated() {
    this.applyInitialView();
  }
  /** Re-evalúa la vista inicial cada render mientras el usuario no haya elegido a mano.
   *
   * `firstUpdated` NO basta: decide una sola vez, y los consumidores que asignan las props por JS
   * DESPUÉS de insertar el elemento —lo normal en páginas renderizadas por el servidor— llegan
   * tarde. En ese momento `cardViewEnabled` aún era `false`, así que no se conmutaba; y el
   * listener de `matchMedia` solo dispara al CAMBIAR el viewport, cosa que en un móvil no pasa
   * nunca. La tabla se quedaba con scroll lateral para siempre.
   *
   * Medido en Android contra producción el 2026-08-02 con el bundle ya actualizado:
   *   `views` antes de insertar  → tarjetas
   *   `views` después de insertar → tabla   ← lo que hace la página
   */
  willUpdate(changed) {
    this.applyInitialView();
    if (changed.has("filterValues")) this.serverFilters = { ...this.filterValues ?? {} };
    if (changed.has("search") && this.search !== void 0) {
      this.q = this.search;
      if (!this.serverSide) {
        this.clientPage = 0;
        this.mobileShown = 0;
      }
    }
    if (!this.serverSide && changed.has("rows") && this.mobileShown !== 0) this.mobileShown = 0;
  }
  applyInitialView() {
    if (this.viewChosenByUser) return;
    if (this.isMobile && this.cardViewEnabled) {
      this.viewMode = "cards";
    } else if (this.defaultView === "cards" && this.cardViewEnabled) {
      this.viewMode = "cards";
    } else if (this.defaultView === "table") {
      this.viewMode = "table";
    }
  }
  setViewMode(mode) {
    this.viewChosenByUser = true;
    if (this.viewMode === mode) return;
    this.viewMode = mode;
    this.emit("viewChange", mode);
  }
  // Control de filtro de una columna, con componentes Ionic (mismos inputs que el form de alta).
  renderFilterControl(col) {
    if (!col.filterable) return A;
    const type = col.filterType ?? "text";
    const f3 = this.filterStateOf(col.key);
    if (type === "select" || type === "multiselect") {
      const multi = type === "multiselect";
      const opts = col.options ?? this.distinctValues(col).map((v3) => ({ value: v3, label: v3 }));
      const current = this.selectValue(f3, multi);
      return b2`
        <ion-select
          label=${col.header}
          label-placement="stacked"
          fill="outline" mode="md"
          ?multiple=${multi}
          interface="modal"
          .interfaceOptions=${{ cssClass: "ok-overlay" }}
          placeholder=${this.t.select}
          .value=${current}
          @ionChange=${(e5) => this.onFilterSelect(col, e5.detail.value, multi)}
        >
          ${multi ? A : b2`<ion-select-option value="">${this.t.select}</ion-select-option>`}
          ${opts.map((o7) => b2`<ion-select-option value=${o7.value}>${o7.label}</ion-select-option>`)}
        </ion-select>
      `;
    }
    if (type === "range" || type === "daterange") {
      const t5 = type === "daterange" ? "date" : "number";
      const onEdge = type === "daterange" ? this.onDateRangeInput.bind(this) : this.onRangeInput.bind(this);
      return b2`
        <div class="fblock">
          <span class="flabel">${col.header}</span>
          <div class="frange">
            <ion-input type=${t5} fill="outline" mode="md" placeholder=${type === "daterange" ? this.t.from : this.t.gte}
              .value=${f3?.from ?? ""}
              @ionInput=${(e5) => onEdge(col, "from", e5)}></ion-input>
            <ion-input type=${t5} fill="outline" mode="md" placeholder=${type === "daterange" ? this.t.to : this.t.lte}
              .value=${f3?.to ?? ""}
              @ionInput=${(e5) => onEdge(col, "to", e5)}></ion-input>
          </div>
        </div>
      `;
    }
    const inputType = type === "number" ? "number" : type === "date" ? "date" : "text";
    return b2`
      <ion-input
        type=${inputType}
        fill="outline" mode="md"
        label=${col.header}
        label-placement="stacked"
        placeholder=${this.t.filterPlaceholder}
        .value=${this.selectValue(f3, false)}
        @ionInput=${(e5) => this.onFilterInput(col, e5)}
      ></ion-input>
    `;
  }
  /** Valor para un control de un solo valor (`ion-select`/`ion-input`) o multi (`ion-select
   *  multiple`) a partir del estado de filtro interno. '' / [] = sin filtro. */
  selectValue(f3, multi) {
    const values = [...f3?.values ?? /* @__PURE__ */ new Set()];
    if (multi) return values;
    return values.length ? values[0] : "";
  }
  // Controles de filtro COMPACTOS para la toolbar (modo `inlineFilters`). Solo select y rango de
  // fechas (los del screenshot); el resto de tipos siguen disponibles vía el drawer si no se activa
  // `inlineFilters`. Look: «Todos los Estados» (placeholder) / «01/10/25 → 18/10/25».
  renderInlineFilters() {
    const cols = this.filterColumns.filter((c5) => {
      const t5 = c5.filterType ?? "text";
      return t5 === "select" || t5 === "multiselect" || t5 === "date" || t5 === "daterange";
    });
    if (!cols.length) return A;
    return b2`${cols.map((c5) => this.renderInlineFilter(c5))}`;
  }
  renderInlineFilter(col) {
    const type = col.filterType ?? "text";
    const f3 = this.filterStateOf(col.key);
    if (type === "select" || type === "multiselect") {
      const multi = type === "multiselect";
      const opts = col.options ?? this.distinctValues(col).map((v3) => ({ value: v3, label: v3 }));
      const current = this.selectValue(f3, multi);
      return b2`
        <ion-select
          class="tk-filter"
          ?multiple=${multi}
          interface="modal"
          .interfaceOptions=${{ cssClass: "ok-overlay" }}
          aria-label=${col.header}
          placeholder=${col.header}
          .value=${current}
          @ionChange=${(e5) => this.onFilterSelect(col, e5.detail.value, multi)}
        >
          ${multi ? A : b2`<ion-select-option value="">${col.header}</ion-select-option>`}
          ${opts.map((o7) => b2`<ion-select-option value=${o7.value}>${o7.label}</ion-select-option>`)}
        </ion-select>
      `;
    }
    return b2`
      <span class="tk-daterange" role="group" aria-label=${col.header}>
        <ion-icon .icon=${iconCalendarOutline}></ion-icon>
        <ion-input type="date" aria-label=${this.t.fromOf.replace("{label}", col.header)} .value=${f3?.from ?? ""} @ionChange=${(e5) => this.onInlineRange(col, "from", e5)}></ion-input>
        <span class="arr">→</span>
        <ion-input type="date" aria-label=${this.t.toOf.replace("{label}", col.header)} .value=${f3?.to ?? ""} @ionChange=${(e5) => this.onInlineRange(col, "to", e5)}></ion-input>
      </span>
    `;
  }
  // Menú overflow («⋮») con ion-popover anclado por evento (Shadow-DOM-safe).
  renderOverflowMenu() {
    if (!this.menuActions.length) return A;
    return b2`
      <ion-button class="toolbtn" fill="clear" aria-label=${this.t.moreActions} @click=${(e5) => this.openMenu(e5)}>
        <ion-icon slot="icon-only" .icon=${iconEllipsisVertical}></ion-icon>
      </ion-button>
      <ion-popover
        .isOpen=${this.menuOpen}
        .event=${this.menuEv}
        dismiss-on-select="true"
        @didDismiss=${() => this.menuOpen = false}
      >
        <ion-content>
          <ion-list lines="none">
            ${this.menuActions.map(
      (a3) => b2`
                <ion-item button .detail=${false} @click=${() => {
        this.menuOpen = false;
        this.emit("menuAction", { actionId: a3.id });
      }}>
                  ${a3.icon ? b2`<ion-icon slot="start" .icon=${okIcon(a3.icon)} style=${ionTone(a3.color, "text") ?? A}></ion-icon>` : A}
                  <ion-label style=${ionTone(a3.color, "text") ?? A}>${a3.label}</ion-label>
                </ion-item>
              `
    )}
          </ion-list>
        </ion-content>
      </ion-popover>
    `;
  }
  // Row action buttons, shared by the table and the card views.
  //
  // `collapsible` = the LIST view, the only one that folds its buttons into a "⋮" menu when the
  // columns leave it no width (#122). The CARD view does not fold; it WRAPS instead, see
  // `.ractions .actions` in the stylesheet.
  //
  // This comment used to claim that a card's actions "always fit across the card". They do not,
  // and nobody had measured it (#132 / ERPlora/appointments#154): with the eight actions an
  // appointment carries, the row asks for 380px and the card gives 379px at 411dp, 237px at 768px
  // and 272px at 1440px — so the first button hung off the card at ALL THREE widths, not just on
  // a phone. If you add a view that lays these buttons out, MEASURE it.
  /** hub#2014 — The row actions that exist for THIS row (`hidden` filtered out), in their order. */
  visibleActions(row) {
    return this.actions.filter((a3) => a3.hidden?.(row) !== true);
  }
  actionButtons(row, collapsible = false) {
    if (!this.actions.length) return A;
    const key = this.keyOf(row);
    const actions = this.visibleActions(row);
    if (collapsible && this.rowActionsCollapsed) {
      if (!actions.length) return b2`<div class="actions"></div>`;
      return b2`
        <div class="actions">
          <ion-button
            size="small"
            fill="clear"
            style=${ionTone("medium", "clear")}
            data-testid=${this.tid(`row-${key}-menu`)}
            aria-label=${this.t.moreActions}
            title=${this.t.moreActions}
            aria-haspopup="menu"
            @click=${(e5) => this.openRowMenu(e5, row)}
          >
            <ion-icon slot="icon-only" .icon=${okIcon(iconEllipsisVertical)}></ion-icon>
          </ion-button>
        </div>
      `;
    }
    return b2`
      <div class="actions">
        ${actions.map(
      (a3) => {
        const loading = a3.loading?.(row) === true;
        const disabled = loading || a3.disabled?.(row) === true;
        const label = typeof a3.label === "function" ? a3.label(row) : a3.label;
        return b2`
            <ion-button
              size="small"
              fill="clear"
              style=${ionTone(a3.color ?? "medium", "clear") ?? A}
              data-testid=${this.tid(`row-${key}-${a3.id}`)}
              ?disabled=${disabled}
              aria-disabled=${disabled ? "true" : A}
              aria-label=${label}
              title=${label}
              @click=${() => this.emit("rowAction", { actionId: a3.id, row })}
            >
              ${loading ? b2`<ion-spinner slot="icon-only" name="dots"></ion-spinner>` : a3.icon ? b2`<ion-icon slot="icon-only" .icon=${okIcon(a3.icon)}></ion-icon>` : label}
            </ion-button>
          `;
      }
    )}
      </div>
    `;
  }
  // Botón de barra icon-only (filtros / alta / conmutador de vista). `on` = estado activo.
  // `badge` opcional → contador (p.ej. nº de filtros activos), look del Hub.
  toolButton(icon, on, onClick, label, badge, testid = A) {
    return b2`
      <ion-button class="toolbtn" size="small" fill=${on ? "solid" : "outline"} data-testid=${testid} title=${label} aria-label=${label} @click=${onClick}>
        <ion-icon slot="icon-only" .icon=${okIcon(icon)}></ion-icon>
        ${badge && badge > 0 ? b2`<span class="badge">${badge}</span>` : A}
      </ion-button>
    `;
  }
  /** Plantilla de columnas del grid de la vista lista: [checkbox] [columnas…] [acciones]. */
  gridTemplate() {
    return [
      this.selectable ? "2.75rem" : null,
      // #120 - 5.5rem (88px) is the narrowest a data column can be and stay readable: ~11
      // characters at 14px, plus the ellipsis `.gcell > span` already applies. With the previous
      // floor (8rem = 128px) the six columns of a bookings list did not fit the counter tablet
      // (128x6 + 188 for actions + gaps = 1036px against 834) and the pinned column ended up on
      // top of the data. With 5.5rem they fit (796px) and `1fr` stretches them to 94px each.
      ...this.visibleColumns.map((c5) => c5.width ?? "minmax(5.5rem,1fr)"),
      // #121 - a LENGTH, not `max-content`. The header and every row are separate grids that
      // share this string, and a content-sized track is not a length: each grid resolves it
      // against ITS OWN content - the word "ACCIONES" (62.83px) in the header, four buttons
      // (188px) in the row. The leftover the `1fr` columns share then differed between the two,
      // and the header slid right, up to 125px by the last column (measured at 834px).
      // `actionsTrackPx` is the width of the buttons MEASURED on screen, so it also keeps #120's
      // contract: the track never shrinks under its content (an `auto` track collapsed to 16px
      // and the buttons spilled over the neighbouring column). Until the first measurement lands
      // - one frame - `max-content` reserves the same room it always did.
      this.actions.length ? this.actionsTrackPx > 0 ? `${this.actionsTrackPx}px` : "max-content" : null
    ].filter(Boolean).join(" ");
  }
  /** Lista de páginas a mostrar en el pager numerado (1-based): primera, última, vecinas de la
   *  actual y «…» donde haya saltos. P.ej. en página 1 de 52 → [1,2,3,'…',52]. */
  pageList(cur1, total) {
    if (total <= 7) return Array.from({ length: total }, (_2, i7) => i7 + 1);
    const want = /* @__PURE__ */ new Set([1, total, cur1, cur1 - 1, cur1 + 1]);
    if (cur1 <= 3) [2, 3].forEach((p4) => want.add(p4));
    if (cur1 >= total - 2) [total - 1, total - 2].forEach((p4) => want.add(p4));
    const sorted = [...want].filter((p4) => p4 >= 1 && p4 <= total).sort((a3, b3) => a3 - b3);
    const out = [];
    let prev = 0;
    for (const p4 of sorted) {
      if (p4 - prev > 1) out.push("\u2026");
      out.push(p4);
      prev = p4;
    }
    return out;
  }
  render() {
    const ps = this.serverSide ? this.pageSize : this.clientPageSize || this.pageSize;
    let visible;
    let pages;
    let current;
    let count;
    if (this.serverSide) {
      visible = this.rows;
      count = this.total;
      pages = Math.max(1, Math.ceil(this.total / ps));
      current = Math.min(this.page, pages - 1);
    } else {
      const filtered = this.clientFiltered;
      count = filtered.length;
      pages = Math.max(1, Math.ceil(filtered.length / ps));
      current = Math.min(this.clientPage, pages - 1);
      visible = this.isMobile ? filtered.slice(0, Math.min(this.mobileShown || ps, count)) : filtered.slice(current * ps, current * ps + ps);
    }
    const served = this.serverSide ? (current + 1) * ps : Math.min(this.mobileShown || ps, count);
    const canLoadMore = this.isMobile && served < count;
    const rangeTo = this.isMobile && !this.serverSide ? Math.min(served, count) : Math.min((current + 1) * ps, count);
    const loadMore = () => {
      if (this.serverSide) this.emit("pageChange", current + 1);
      else this.mobileShown = Math.min((this.mobileShown || ps) + ps, count);
    };
    const goTo = (p4) => {
      if (this.serverSide) this.emit("pageChange", p4);
      else this.clientPage = p4;
    };
    const setPageSize = (n6) => {
      if (this.serverSide) this.emit("pageSizeChange", n6);
      else {
        this.clientPageSize = n6;
        this.clientPage = 0;
        this.mobileShown = 0;
      }
    };
    const searchbar = b2`<ion-searchbar class="ion-no-border" data-testid=${this.tid("search")} .value=${this.q} placeholder=${this.effSearchPlaceholder} debounce="250" @ionInput=${this.onSearch}></ion-searchbar>`;
    const selCount = this.selection.size;
    const showTopbar = !!this.title || this.hasSearch || this.viewToggle || this.effColumnPicker || this.effExport || this.effImport || this.hasFilterRow || this.addable || !!this.primaryAction;
    return b2`
      <div class=${`card${this.panel !== "none" ? " has-panel" : ""}`}>
        ${showTopbar ? b2`
              <div class="bar">
                <div class="bar-main">
                  ${this.title ? b2`<div class="title-wrap"><h2 class="title">${this.title}</h2><span class="title-count">${count}</span></div>` : A}
                  ${this.hasSearch ? b2`<div class="search">${searchbar}</div>` : A}
                  ${this.inlineFilters ? this.renderInlineFilters() : A}
                  <span class="tk-spacer"></span>
                    ${this.effColumnPicker && !this.isMobile ? b2`
                          <ion-select
                            class="tk-cols"
                            multiple
                            interface="popover"
                            aria-label=${this.t.columnsVisible}
                            .value=${this.visibleColumns.map((c5) => c5.key)}
                            .selectedText=${this.t.columns}
                            @ionChange=${(e5) => this.setVisibleColumns(e5.detail.value)}
                          >
                            ${this.columns.map((c5) => b2`<ion-select-option value=${c5.key}>${c5.header}</ion-select-option>`)}
                          </ion-select>
                        ` : A}
                    ${this.effPageSizes.length && !this.isMobile ? b2`
                          <ion-select
                            class="tk-psize"
                            interface="popover"
                            aria-label=${this.t.rowsPerPage}
                            .value=${ps}
                            @ionChange=${(e5) => setPageSize(Number(e5.detail.value))}
                          >
                            ${this.effPageSizes.map((n6) => b2`<ion-select-option .value=${n6}>${n6}</ion-select-option>`)}
                          </ion-select>
                        ` : A}
                    ${this.viewToggle ? b2`
                          <span class="viewseg">
                            ${this.toolButton("list-outline", this.viewMode === "table", () => this.setViewMode("table"), this.t.viewList)}
                            ${this.toolButton("grid-outline", this.viewMode === "cards", () => this.setViewMode("cards"), this.t.viewCards)}
                          </span>
                        ` : A}
                    ${this.hasFilterRow && !this.inlineFilters ? this.toolButton("funnel-outline", this.panel === "filters" || this.activeFilterCount > 0, () => this.toggle("filters"), this.t.filters, this.activeFilterCount) : A}
                    ${this.effImport ? b2`
                          ${this.toolButton("cloud-upload-outline", false, () => this.renderRoot.querySelector(".tk-file")?.click(), this.t.importCsv)}
                          <!-- #143 — The import hook goes on the INPUT, not on the button that
                               triggers it: what a spec drives is «setInputFiles», and nobody opens
                               the button's native dialog from a test. Same criterion as
                               «GrantFilePicker.vue» in the Hub (the hook goes on the control, not
                               on its disguise). -->
                          <input class="tk-file" data-testid=${this.tid("csv-import")} type="file" accept=".csv,text/csv" hidden @change=${(e5) => this.onImportFile(e5)} />
                        ` : A}
                    ${this.effExport ? this.toolButton("download-outline", false, () => this.exportCsv(), this.t.exportCsv, void 0, this.tid("csv-export")) : A}
                    <!-- #113 — Mismo botón en los dos viewports: la acción principal de la pantalla
                         se lee, no se adivina. En escritorio era un «+» de 36px idéntico a los
                         iconos de vista/filtrar/exportar, y era el último de cuatro. -->
                    ${this.addable ? b2`
                          <ion-button class="primary-btn add-btn" data-testid=${this.tid("add")} size="small" @click=${() => this.toggle("create")}>
                            <ion-icon slot="start" .icon=${okIcon("add")}></ion-icon>${this.t.add}
                          </ion-button>
                        ` : A}
                    ${this.renderOverflowMenu()}
                    ${this.primaryAction ? b2`
                          <!-- #143 — Its own hook and NOT «-add»: «addable» and «primaryAction» are
                               two different buttons that may coexist, and both are really used
                               («addable» in the modules, «primaryAction» in the SaaS screens).
                               Sharing the name would give two elements with the same hook as soon
                               as a screen declared both. -->
                          <ion-button class="primary-btn add-btn" data-testid=${this.tid("primary-action")} size="small" @click=${() => this.emit("primaryAction", {})}>
                            <ion-icon slot="start" .icon=${okIcon(this.primaryAction.icon ?? "add")}></ion-icon>${this.primaryAction.label}
                          </ion-button>
                        ` : A}
                    <!-- El módulo proyecta aquí acciones globales adicionales. -->
                    <slot name="toolbar"></slot>
                </div>
                ${this.selectable && selCount > 0 ? b2`
                      <div class="selbar">
                        <strong>${this.t.selected.replace("{n}", String(selCount))}</strong>
                        <button class="sel-clear" @click=${() => this.setSelection(/* @__PURE__ */ new Set())}>
                          <ion-icon .icon=${iconClose} style="font-size:14px"></ion-icon> ${this.t.clear}
                        </button>
                      </div>
                    ` : A}
              </div>
            ` : A}

        ${this.viewMode === "cards" && this.cardViewEnabled ? this.renderCards(visible) : this.renderTable(visible)}

        ${pages > 1 || this.effPageSizes.length ? b2`
              <div class="pager">
                <div class="left">
                  <span>
                    ${pages > 1 ? b2`${this.t.showing.replace("{from}", String(this.isMobile && !this.serverSide ? 1 : current * ps + 1)).replace("{to}", String(rangeTo))} ` : A}
                    <span class="strong">${count}</span> ${count === 1 ? this.t.recordSingular : this.t.recordPlural}
                  </span>
                  ${!showTopbar && this.effPageSizes.length ? b2`
                        <select class="psize" @change=${(e5) => setPageSize(Number(e5.target.value))}>
                          ${this.effPageSizes.map((n6) => b2`<option value=${n6} ?selected=${n6 === ps}>${this.t.perPageShort.replace("{n}", String(n6))}</option>`)}
                        </select>
                      ` : A}
                </div>
                ${this.isMobile ? canLoadMore ? b2`<ion-button class="load-more" data-testid=${this.tid("load-more")} size="small" @click=${loadMore}>${this.t.loadMore}</ion-button>` : A : pages > 1 ? b2`
                      <div class="nav">
                        <ion-button size="small" fill="clear" data-testid=${this.tid("page-prev")} ?disabled=${current === 0} @click=${() => goTo(current - 1)}><ion-icon slot="icon-only" .icon=${iconChevronBack}></ion-icon></ion-button>
                        ${this.pageList(current + 1, pages).map(
      (p4) => p4 === "\u2026" ? b2`<span class="pgap">…</span>` : b2`<button class=${`pnum${p4 === current + 1 ? " on" : ""}`} @click=${() => goTo(p4 - 1)}>${p4}</button>`
    )}
                        <ion-button size="small" fill="clear" data-testid=${this.tid("page-next")} ?disabled=${current >= pages - 1} @click=${() => goTo(current + 1)}><ion-icon slot="icon-only" .icon=${iconChevronForward}></ion-icon></ion-button>
                      </div>
                    ` : A}
              </div>
            ` : A}

        ${this.panel !== "none" ? this.renderDrawer() : A}
      </div>
    `;
  }
  // Panel lateral derecho DENTRO de la tabla (no empuja contenido; igual en lista y tarjetas).
  renderDrawer() {
    const isFilters = this.panel === "filters";
    const clientFilters = isFilters && !this.serverSide;
    return b2`
      <div class="tk-scrim" @click=${() => this.close()}></div>
      <aside class="drawer" role="dialog" aria-label=${isFilters ? this.t.filters : this.t.form}>
        <header class="dh">
          <strong>${isFilters ? this.t.filters : this.t.newRecord}</strong>
          <ion-button fill="clear" size="small" aria-label=${this.t.close} @click=${() => this.close()}><ion-icon slot="icon-only" .icon=${iconClose}></ion-icon></ion-button>
        </header>
        <div class="db">
          ${isFilters ? clientFilters ? this.filterColumns.map((c5) => this.renderClientFilter(c5)) : this.filterColumns.map((c5) => b2`<div class="fblock">${this.renderFilterControl(c5)}</div>`) : b2`<slot name="create"></slot>`}
        </div>
        ${clientFilters ? b2`
              <footer class="df">
                <button class="sel-clear df-clear" ?disabled=${Object.keys(this.filterDraft).length === 0} @click=${() => this.clearFilters()}>${this.t.clear}</button>
                <ion-button class="primary-btn" size="small" @click=${() => this.applyFilters()}>${this.t.apply}</ion-button>
              </footer>
            ` : A}
      </aside>
    `;
  }
  // Control de filtro CLIENTE de una columna: chips multi-select (select) o rango de fechas.
  renderClientFilter(col) {
    const label = col.header;
    if (col.filterType === "daterange" || col.filterType === "date") {
      const f3 = this.filterDraft[col.key] ?? {};
      return b2`
        <div class="fblock">
          <span class="flabel">${label}</span>
          <div class="daterange">
            <ion-input type="date" label=${this.t.from} label-placement="stacked" fill="outline" mode="md" .value=${f3.from ?? ""} @ionChange=${(e5) => this.setFilterRange(col.key, "from", e5.detail.value ?? "")}></ion-input>
            <ion-input type="date" label=${this.t.to} label-placement="stacked" fill="outline" mode="md" .value=${f3.to ?? ""} @ionChange=${(e5) => this.setFilterRange(col.key, "to", e5.detail.value ?? "")}></ion-input>
          </div>
        </div>
      `;
    }
    const opts = col.options ?? this.distinctValues(col).map((v3) => ({ value: v3, label: v3 }));
    const selected = [...this.filterDraft[col.key]?.values ?? /* @__PURE__ */ new Set()];
    return b2`
      <div class="fblock">
        <ion-select
          label=${label}
          label-placement="stacked"
          fill="outline" mode="md"
          multiple
          interface="modal"
          .interfaceOptions=${{ cssClass: "ok-overlay" }}
          placeholder=${this.t.select}
          .value=${selected}
          @ionChange=${(e5) => this.setFilterValues(col.key, e5.detail.value ?? [])}
        >
          ${opts.length === 0 ? b2`<ion-select-option .disabled=${true} value="">${this.t.noValues}</ion-select-option>` : opts.map((o7) => b2`<ion-select-option value=${o7.value}>${o7.label}</ion-select-option>`)}
        </ion-select>
      </div>
    `;
  }
  /** #67 — Enter/Espacio activan la fila clicable (y, desde #74, la tarjeta): si se llega con el
   *  tabulador, el ratón no puede ser el único camino. Espacio además NO debe desplazar la página. */
  onRowKeydown(e5, row) {
    if (e5.key !== "Enter" && e5.key !== " " && e5.key !== "Spacebar") return;
    e5.preventDefault();
    this.emit("rowClick", { row });
  }
  emptyState() {
    const noMatches = this.rows.length > 0;
    return b2`
      <div class="empty">
        <span class="empty-ic"><ion-icon .icon=${iconFileTrayOutline}></ion-icon></span>
        <span>${noMatches ? this.effNoMatchesMessage : this.effEmptyMessage}</span>
        ${noMatches ? b2`<ion-button fill="clear" size="small" data-role="no-matches-reset" data-testid=${this.tid("show-all")} @click=${() => this.resetSearchAndFilters()}>${this.t.showAll}</ion-button>` : A}
      </div>
    `;
  }
  // Vista LISTA en CSS GRID (no <table>): permite ancho por columna y cabecera sticky.
  renderTable(visible) {
    if (visible.length === 0) return this.emptyState();
    const cols = this.visibleColumns;
    const tpl = { gridTemplateColumns: this.gridTemplate() };
    const allOn = this.selectable && visible.length > 0 && visible.every((r6) => this.selection.has(this.keyOf(r6)));
    const alignCls = (a3) => a3 === "right" ? "right" : a3 === "center" ? "center" : "left";
    return b2`
      <div class=${`scroll${this.xOverflow ? " x-overflow" : ""}`}>
        <div class="grid" role="table">
          <!-- Cabecera -->
          <div class="grow ghead" role="row" style=${o6(tpl)}>
            ${this.selectable ? b2`<span class="selcb"><ion-checkbox .checked=${allOn} aria-label=${this.t.selectAll} @ionChange=${() => this.toggleAll(visible)}></ion-checkbox></span>` : A}
            ${cols.map((c5) => {
      const sortable = this.isSortable(c5);
      const active = sortable && (this.serverSide ? this.sort === c5.key : this.clientSort === c5.key);
      const dir = this.serverSide ? this.sortDir : this.clientSortDir;
      const caretIcon = !active ? iconSwapVerticalOutline : dir === "asc" ? iconChevronUpOutline : iconChevronDownOutline;
      return b2`
                <div
                  class=${`gcell gh ${alignCls(c5.align)}${sortable ? " sortable" : ""}${c5.pinned === "end" ? " actions-col" : ""}`}
                  role="columnheader"
                  @click=${() => this.onHeaderClick(c5)}
                >
                  <span>${c5.header}</span>
                  ${sortable ? b2`<span class=${`caret${active ? " on" : ""}`}><ion-icon .icon=${okIcon(caretIcon)}></ion-icon></span>` : A}
                </div>
              `;
    })}
            ${this.actions.length ? b2`<div class="gcell gh right actions-col" role="columnheader">
                  ${this.rowActionsCollapsed ? b2`<span class="sr-only">${this.t.actions}</span>` : b2`<span>${this.t.actions}</span>`}
                </div>` : A}
          </div>

          <!-- Filas -->
          ${c4(
      visible,
      (row) => this.keyOf(row),
      (row) => {
        const key = this.keyOf(row);
        const selected = this.selectable && this.selection.has(key);
        return b2`
                <div
                  class=${`grow grow-data${selected ? " selected" : ""}${this.rowClickable ? " clickable" : ""}`}
                  role="row"
                  data-testid=${this.tid(`row-${key}`)}
                  style=${o6(tpl)}
                  tabindex=${this.rowClickable ? "0" : A}
                  @click=${this.rowClickable ? () => this.emit("rowClick", { row }) : A}
                  @keydown=${this.rowClickable ? (e5) => this.onRowKeydown(e5, row) : A}
                >
                  ${this.selectable ? b2`<span class="selcb" @click=${(e5) => e5.stopPropagation()}><ion-checkbox .checked=${selected} aria-label=${this.t.selectRow} @ionChange=${() => this.toggleRow(key)}></ion-checkbox></span>` : A}
                  ${cols.map(
          (c5) => b2`<div class=${`gcell ${alignCls(c5.align)}${c5.pinned === "end" ? " actions-col" : ""}`} role="cell">${c5.render ? c5.render(row) : b2`<span>${this.cell(c5, row)}</span>`}</div>`
        )}
                  ${this.actions.length ? b2`<div class="gcell right actions-col" role="cell" @click=${(e5) => e5.stopPropagation()}>${this.actionButtons(row, true)}</div>` : A}
                </div>
              `;
      }
    )}
        </div>
      </div>
      ${this.renderRowMenu()}
    `;
  }
  renderCards(visible) {
    if (visible.length === 0) return this.emptyState();
    const hasHead = !!this.cardTitle || !!this.cardIcon || this.selectable;
    return b2`
      <div class="cards-grid">
        ${c4(
      visible,
      (row) => this.keyOf(row),
      (row) => {
        const key = this.keyOf(row);
        const selected = this.selectable && this.selection.has(key);
        const icon = this.cardIcon?.(row);
        return b2`
              <ion-card
                class=${`rcard${selected ? " selected" : ""}${this.rowClickable ? " clickable" : ""}`}
                data-testid=${this.tid(`row-${key}`)}
                role=${this.rowClickable ? "button" : A}
                tabindex=${this.rowClickable ? "0" : A}
                @click=${this.rowClickable ? () => this.emit("rowClick", { row }) : A}
                @keydown=${this.rowClickable ? (e5) => this.onRowKeydown(e5, row) : A}
              >
                ${hasHead ? b2`
                      <ion-card-header class="rcard-head">
                        ${icon != null && icon !== "" ? b2`<span class="rc-icon">${typeof icon === "string" ? b2`<ion-icon .icon=${okIcon(icon)}></ion-icon>` : icon}</span>` : A}
                        <span class="rc-title">${this.cardTitle ? this.cardTitle(row) : A}</span>
                        ${this.selectable ? b2`<ion-checkbox .checked=${selected} aria-label=${this.t.select} @click=${(e5) => e5.stopPropagation()} @ionChange=${() => this.toggleRow(key)}></ion-checkbox>` : A}
                      </ion-card-header>
                    ` : A}
                <ion-card-content class="rcard-body">
                  ${this.renderCard ? this.renderCard(row) : this.visibleColumns.map(
          (c5) => b2`<div class="rrow"><span class="rk">${c5.header}</span><span class="rv">${c5.render ? c5.render(row) : this.cell(c5, row)}</span></div>`
        )}
                </ion-card-content>
                ${this.actions.length ? b2`<div class="ractions" @click=${(e5) => e5.stopPropagation()}>${this.actionButtons(row)}</div>` : A}
              </ion-card>
            `;
      }
    )}
      </div>
    `;
  }
};
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "columns");
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "rows");
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "searchKeys");
__decorateClass2([
  n4({ attribute: "row-key-field" })
], _OkDataTable.prototype, "rowKeyField");
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "rowKey");
__decorateClass2([
  n4({ type: Number, attribute: "page-size" })
], _OkDataTable.prototype, "pageSize");
__decorateClass2([
  n4({ attribute: "empty-message" })
], _OkDataTable.prototype, "emptyMessage");
__decorateClass2([
  n4({ attribute: "no-matches-message" })
], _OkDataTable.prototype, "noMatchesMessage");
__decorateClass2([
  n4({ attribute: "search-placeholder" })
], _OkDataTable.prototype, "searchPlaceholder");
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "labels");
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "actions");
__decorateClass2([
  n4({ type: Boolean })
], _OkDataTable.prototype, "addable");
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "pageSizeOptions");
__decorateClass2([
  n4({ type: Boolean, reflect: true })
], _OkDataTable.prototype, "fill");
__decorateClass2([
  n4({ type: Boolean, attribute: "column-picker" })
], _OkDataTable.prototype, "columnPicker");
__decorateClass2([
  n4({ type: Boolean })
], _OkDataTable.prototype, "csv");
__decorateClass2([
  n4({ attribute: "csv-name" })
], _OkDataTable.prototype, "csvName");
__decorateClass2([
  n4({ type: Boolean, attribute: "server-side" })
], _OkDataTable.prototype, "serverSide");
__decorateClass2([
  n4({ type: Number })
], _OkDataTable.prototype, "total");
__decorateClass2([
  n4({ type: Number })
], _OkDataTable.prototype, "page");
__decorateClass2([
  n4({ type: Boolean })
], _OkDataTable.prototype, "searchable");
__decorateClass2([
  n4({ type: String })
], _OkDataTable.prototype, "search");
__decorateClass2([
  n4({ type: String })
], _OkDataTable.prototype, "sort");
__decorateClass2([
  n4({ attribute: "sort-dir" })
], _OkDataTable.prototype, "sortDir");
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "filterValues");
__decorateClass2([
  n4()
], _OkDataTable.prototype, "title");
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "views");
__decorateClass2([
  n4({ attribute: "default-view" })
], _OkDataTable.prototype, "defaultView");
__decorateClass2([
  n4({ type: Boolean })
], _OkDataTable.prototype, "exportable");
__decorateClass2([
  n4({ type: Boolean })
], _OkDataTable.prototype, "importable");
__decorateClass2([
  n4({ type: Boolean, attribute: "column-selector" })
], _OkDataTable.prototype, "columnSelector");
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "pageSizes");
__decorateClass2([
  n4({ type: Boolean, attribute: "row-clickable" })
], _OkDataTable.prototype, "rowClickable");
__decorateClass2([
  n4({ type: Boolean })
], _OkDataTable.prototype, "selectable");
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "selectedKeys");
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "primaryAction");
__decorateClass2([
  n4({ type: Boolean })
], _OkDataTable.prototype, "inlineFilters");
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "menuActions");
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "cardTitle");
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "cardIcon");
__decorateClass2([
  n4({ attribute: false })
], _OkDataTable.prototype, "renderCard");
__decorateClass2([
  n4({ type: String })
], _OkDataTable.prototype, "testid");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "q");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "clientPage");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "clientPageSize");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "mobileShown");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "clientSort");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "clientSortDir");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "clientFilters");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "filterDraft");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "serverFilters");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "panel");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "viewMode");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "isMobile");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "xOverflow");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "actionsTrackPx");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "rowActionsCollapsed");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "rowMenuOpen");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "hiddenKeys");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "internalSelection");
__decorateClass2([
  r5()
], _OkDataTable.prototype, "menuOpen");
var OkDataTable = _OkDataTable;
define("ok-data-table", OkDataTable);

// @erplora/outfitkit/dist/ok-status-pill.js
var __defProp3 = Object.defineProperty;
var __decorateClass3 = (decorators, target, key, kind) => {
  var result = void 0;
  for (var i7 = decorators.length - 1, decorator; i7 >= 0; i7--)
    if (decorator = decorators[i7])
      result = decorator(target, key, result) || result;
  if (result) __defProp3(target, key, result);
  return result;
};
var OkStatusPill = class extends i3 {
  constructor() {
    super(...arguments);
    this.tone = "neutral";
    this.dot = false;
    this.size = "md";
  }
  static {
    this.styles = i`
    :host {
      /* Vars overridable (estilo Ionic), default = cadena --ok-* → --ion-* → hex.
         --tone-color (base: fondo/punto/icono) y --tone-shade (texto) se reasignan por tone abajo. */
      --tone-color: var(--ok-medium, var(--ion-color-medium, #5f5f5f));
      --tone-shade: var(--ok-medium, var(--ion-color-medium-shade, #545454));
      --background-opacity: var(--ok-pill-bg-opacity, 0.14);
      --border-radius: var(--ok-pill-radius, 999px);
      --font: var(--ok-font, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif);

      /* Inline: el pill vive en celdas de tabla, cabeceras y listados. */
      display: inline-flex;
      vertical-align: middle;
      font-family: var(--font);
      box-sizing: border-box;
    }

    /* Mapa de tonos → color Ionic (base + shade para el texto). */
    :host([tone='success']) {
      --tone-color: var(--ok-success, var(--ion-color-success, #2dd55b));
      --tone-shade: var(--ok-success, var(--ion-color-success-shade, #28bb50));
    }
    :host([tone='warning']) {
      --tone-color: var(--ok-warning, var(--ion-color-warning, #ffc409));
      --tone-shade: var(--ok-warning-shade, var(--ion-color-warning-shade, #e0ac08));
    }
    :host([tone='danger']) {
      --tone-color: var(--ok-danger, var(--ion-color-danger, #c5000f));
      --tone-shade: var(--ok-danger, var(--ion-color-danger-shade, #ad000d));
    }
    :host([tone='info']) {
      --tone-color: var(--ok-info, var(--ion-color-secondary, #0163aa));
      --tone-shade: var(--ok-info, var(--ion-color-secondary-shade, #015896));
    }
    :host([tone='primary']) {
      --tone-color: var(--ok-primary, var(--ion-color-primary, #3880ff));
      --tone-shade: var(--ok-primary, var(--ion-color-primary-shade, #3171e0));
    }
    /* neutral / sin tono → medium (default ya aplicado en :host). */

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 0.4em;
      padding: 0.25em 0.7em;
      border-radius: var(--border-radius);
      /* Fondo tonal: el color del tono con baja opacidad. */
      background: color-mix(in srgb, var(--tone-color) calc(var(--background-opacity) * 100%), transparent);
      color: var(--ok-pill-color, var(--tone-shade));
      font-size: 0.8125rem;
      font-weight: 600;
      line-height: 1.4;
      white-space: nowrap;
    }
    :host([size='sm']) .pill {
      font-size: 0.72rem;
      padding: 0.2em 0.6em;
    }

    ion-icon {
      flex: 0 0 auto;
      font-size: 1.05em;
      pointer-events: none;
    }

    /* Punto de color (estilo Linear) en vez de icono. */
    .dot {
      flex: 0 0 auto;
      width: 0.5em;
      height: 0.5em;
      border-radius: 50%;
      background: var(--tone-color);
    }
  `;
  }
  render() {
    return b2`
      <span class="pill" part="pill">
        ${this.dot ? b2`<span class="dot" part="dot" aria-hidden="true"></span>` : this.icon ? b2`<ion-icon .icon=${okIcon(this.icon)} aria-hidden="true"></ion-icon>` : null}
        <slot>${this.label ?? ""}</slot>
      </span>
    `;
  }
};
__decorateClass3([
  n4({ type: String, reflect: true })
], OkStatusPill.prototype, "tone");
__decorateClass3([
  n4({ type: String })
], OkStatusPill.prototype, "label");
__decorateClass3([
  n4({ type: String })
], OkStatusPill.prototype, "icon");
__decorateClass3([
  n4({ type: Boolean, reflect: true })
], OkStatusPill.prototype, "dot");
__decorateClass3([
  n4({ type: String, reflect: true })
], OkStatusPill.prototype, "size");
define("ok-status-pill", OkStatusPill);

// @erplora/outfitkit/dist/shared/fullscreen.js
function notCapable() {
  return Promise.reject(new Error("Not capable"));
}
function isCapable(target) {
  if (typeof document === "undefined") return false;
  if (document.fullscreenEnabled === false) return false;
  const el = target ?? document.documentElement;
  return typeof el?.requestFullscreen === "function";
}
function activeEl() {
  if (typeof document === "undefined") return null;
  return document.fullscreenElement ?? null;
}
function isActive(el) {
  if (typeof document === "undefined") return false;
  if (!el) return activeEl() !== null;
  const root = el.getRootNode();
  if (root !== document && root.fullscreenElement === el) return true;
  return document.fullscreenElement === el;
}
function request(target) {
  if (typeof document === "undefined") return notCapable();
  const el = target ?? document.documentElement;
  if (!isCapable(el)) return notCapable();
  return el.requestFullscreen();
}
function exit() {
  if (typeof document === "undefined") return Promise.resolve();
  if (activeEl() === null) return Promise.resolve();
  const exitFn = document.exitFullscreen;
  if (typeof exitFn !== "function") return notCapable();
  return exitFn.call(document);
}
function toggle(target) {
  return isActive(target) ? exit() : request(target);
}
function onChange(fn) {
  if (typeof document === "undefined") return () => {
  };
  const handler = () => fn(activeEl());
  document.addEventListener("fullscreenchange", handler);
  let stopped = false;
  return () => {
    if (stopped) return;
    stopped = true;
    document.removeEventListener("fullscreenchange", handler);
  };
}

// @erplora/outfitkit/dist/shared/tap-target.js
var tapTarget = i`
  /* The host positions itself. Leaving this to each component was not a contract but a trap: an
     absolutely positioned overlay resolves against the nearest POSITIONED ancestor, so a host that
     forgot position:relative sent its hit area somewhere else entirely -- ok-color-picker shipped
     with its 10 preset swatches stacked in the middle of the panel, over the saturation square,
     where a click set the colour to #000000.
     A component that genuinely needs another value declares it in its own rule, which comes later in
     static styles and wins. */
  .ok-tap,
  [data-ok-tap] {
    position: relative;
  }

  .ok-tap::before,
  [data-ok-tap]::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: max(100%, var(--ok-tap-min, 44px));
    height: max(100%, var(--ok-tap-min, 44px));
  }
`;

// @erplora/outfitkit/dist/ok-lightbox.js
var __defProp4 = Object.defineProperty;
var __decorateClass4 = (decorators, target, key, kind) => {
  var result = void 0;
  for (var i7 = decorators.length - 1, decorator; i7 >= 0; i7--)
    if (decorator = decorators[i7])
      result = decorator(target, key, result) || result;
  if (result) __defProp4(target, key, result);
  return result;
};
var DEFAULT_LABELS2 = {
  prev: "Previous",
  next: "Next",
  close: "Close",
  download: "Download",
  fullscreen: "Fullscreen",
  exitFullscreen: "Exit fullscreen"
};
var OkLightbox = class extends i3 {
  constructor() {
    super(...arguments);
    this.items = [];
    this.index = 0;
    this.open = false;
    this.labels = {};
    this.shown = false;
    this.fullscreenOn = false;
    this.portalRoot = null;
    this.onKeydown = (e5) => {
      if (!this.open) return;
      if (e5.key === "Escape") {
        e5.preventDefault();
        this.requestClose();
      } else if (e5.key === "ArrowLeft") {
        e5.preventDefault();
        this.go(-1);
      } else if (e5.key === "ArrowRight") {
        e5.preventDefault();
        this.go(1);
      }
    };
  }
  static {
    this.styles = [tapTarget, i`
    :host {
      display: block;
      width: 100%;
      /* Vars overridable (estilo Ionic), default = cadena --ok-* → --ion-* → hex/literal. */
      --overlay-bg: var(--ok-media-bg, rgba(0, 0, 0, 0.92));
      --fg-soft: var(--ok-media-fg, rgba(255, 255, 255, 0.7));
      --glass: var(--ok-overlay-glass, rgba(255, 255, 255, 0.1));
      --glass-hover: var(--ok-overlay-glass-2, rgba(255, 255, 255, 0.18));
      --brand: var(--ok-primary, var(--ion-color-primary, #e8552a));
      --media-bg: var(--ok-media-frame, rgba(255, 255, 255, 0.06));
      --radius-lg: var(--ok-radius-lg, 10px);
      --radius-sm: var(--ok-radius-sm, 6px);
      --font: var(--ok-font, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif);
      --font-mono: var(--ok-font-mono, ui-monospace, 'SF Mono', 'Cascadia Code', Menlo, monospace);
    }

    /* Overlay a pantalla completa: columna [cabecera | medio | filmstrip]. */
    .lightbox {
      position: fixed;
      inset: 0;
      z-index: 1000;
      display: flex;
      flex-direction: column;
      padding: 20px;
      box-sizing: border-box;
      background: var(--overlay-bg);
      color: var(--fg-soft);
      font-family: var(--font);
      opacity: 0;
      transition: opacity var(--ok-transition, 200ms ease);
    }
    .lightbox.shown {
      opacity: 1;
    }
    @media (prefers-reduced-motion: reduce) {
      .lightbox {
        transition: none;
      }
    }

    /* Cabecera mono: contador + nombre a la izquierda; acciones a la derecha. */
    .head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      font-family: var(--font-mono);
      font-size: 12px;
      color: var(--fg-soft);
    }
    .head .meta {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .head .count {
      font-variant-numeric: tabular-nums;
    }
    .head .sep {
      opacity: 0.5;
      margin: 0 6px;
    }
    .head .actions {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      flex: none;
    }
    .icon-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: var(--ok-tap-min, 44px);
      height: var(--ok-tap-min, 44px);
      padding: 0;
      border: 0;
      border-radius: 50%;
      background: transparent;
      color: var(--fg-soft);
      cursor: pointer;
      text-decoration: none;
      transition: background var(--ok-transition, 150ms ease), color var(--ok-transition, 150ms ease);
    }
    @media (hover: hover) {
      .icon-btn:hover {
        background: var(--glass);
        color: #fff;
      }
    }
    .icon-btn ion-icon {
      font-size: 1.25rem;
    }

    /* Zona central: medio centrado con flechas de navegación absolutas. */
    .main {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 16px 0;
      position: relative;
      min-height: 0;
    }
    .media {
      max-width: 60%;
      max-height: 100%;
      width: auto;
      object-fit: contain;
      background: var(--media-bg);
      border-radius: var(--radius-lg);
      display: block;
    }
    /* Reserva de proporción 16:10 cuando no hay medio o como marco de fondo. */
    .media-empty {
      width: 60%;
      aspect-ratio: 16 / 10;
      max-height: 100%;
      background: var(--media-bg);
      border-radius: var(--radius-lg);
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: var(--font-mono);
      font-size: 12px;
      color: var(--fg-soft);
    }
    video.media {
      max-height: 100%;
    }
    /* Phones: the 60% cap painted the photo smaller than its thumbnail in the conversation (#175);
       use the full width like any phone gallery. The nav arrows stay on top of the media. */
    @media (max-width: 767px) {
      .media {
        max-width: 100%;
      }
      .media-empty {
        width: 100%;
      }
    }

    /* Navegación circular glass de 44px. */
    .nav {
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      width: 44px;
      height: 44px;
      border-radius: 50%;
      border: 0;
      background: var(--glass);
      color: #fff;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      backdrop-filter: blur(4px);
      transition: background var(--ok-transition, 150ms ease), opacity var(--ok-transition, 150ms ease);
    }
    @media (hover: hover) {
      .nav:hover {
        background: var(--glass-hover);
      }
    }
    .nav[disabled] {
      opacity: 0.25;
      cursor: default;
      pointer-events: none;
    }
    .nav ion-icon {
      font-size: 1.5rem;
    }
    .nav.prev {
      left: 20px;
    }
    .nav.next {
      right: 20px;
    }

    /* Filmstrip inferior: miniaturas 50×36, la activa a opacidad total con outline de marca. */
    .strip {
      display: flex;
      gap: 6px;
      justify-content: center;
      flex-wrap: wrap;
      padding-top: 12px;
      max-height: 96px;
      overflow-x: auto;
      overflow-y: hidden;
    }
    .thumb {
      /* ok-tap-exempt: filmstrip thumbnail, 50x36 is the drawn size of the strip; growing it
         would reflow the whole strip's composition. The hit area is widened by tapTarget
         instead (its ::before below), the drawing stays put. */
      position: relative;
      flex: none;
      width: 50px;
      height: 36px;
      padding: 0;
      border: 0;
      border-radius: var(--radius-sm);
      background: var(--media-bg);
      background-size: cover;
      background-position: center;
      cursor: pointer;
      opacity: 0.5;
      /* No overflow:hidden here: it would clip tapTarget's ::before hit-area extension along
         with the drawing. The rounded corners are clipped on the children instead (below). */
      transition: opacity var(--ok-transition, 150ms ease);
    }
    @media (hover: hover) {
      .thumb:hover {
        opacity: 0.8;
      }
    }
    .thumb.active {
      opacity: 1;
      outline: 2px solid var(--brand);
      outline-offset: 2px;
    }
    .thumb img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      border-radius: inherit;
    }
    .thumb .vid {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 100%;
      color: var(--fg-soft);
      border-radius: inherit;
      overflow: hidden;
    }
    .thumb .vid ion-icon {
      font-size: 1rem;
    }
  `];
  }
  // Textos efectivos: defaults en inglés + overrides del consumidor.
  get t() {
    return { ...DEFAULT_LABELS2, ...this.labels };
  }
  connectedCallback() {
    super.connectedCallback();
    this.stopFullscreenWatch = onChange(() => {
      this.fullscreenOn = isActive(this.boxEl() ?? void 0);
    });
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    this.stopFullscreenWatch?.();
    this.stopFullscreenWatch = void 0;
    this.unbind();
    const host = this.portalRoot?.host;
    this.portalRoot = null;
    if (host && host.parentNode) host.parentNode.removeChild(host);
  }
  bind() {
    document.addEventListener("keydown", this.onKeydown);
  }
  unbind() {
    document.removeEventListener("keydown", this.onKeydown);
  }
  // Crea (una vez) el portal: un div en `document.body` con shadow propio que ADOPTA la misma hoja
  // de estilos del componente.
  ensurePortal() {
    if (this.portalRoot) return this.portalRoot;
    const host = document.createElement("div");
    host.setAttribute("data-ok-lightbox-portal", "");
    document.body.appendChild(host);
    const root = host.attachShadow({ mode: "open" });
    const styles = this.constructor.elementStyles ?? [];
    root.adoptedStyleSheets = styles.map((s5) => s5 instanceof CSSStyleSheet ? s5 : s5.styleSheet).filter((s5) => !!s5);
    this.portalRoot = root;
    return root;
  }
  updated(changed) {
    if (changed.has("open")) {
      if (this.open) {
        this.bind();
        requestAnimationFrame(() => requestAnimationFrame(() => this.shown = true));
      } else {
        this.unbind();
        this.shown = false;
      }
    }
    if (!this.open && !this.portalRoot) return;
    D(this.open ? this.overlayTemplate() : A, this.ensurePortal());
  }
  // Índice saneado dentro de los límites.
  get safeIndex() {
    const n6 = this.items.length;
    if (n6 === 0) return 0;
    return Math.max(0, Math.min(this.index, n6 - 1));
  }
  prefersReducedMotion() {
    return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
  }
  // Navega delta posiciones (clamp, sin wrap). Emite `ok-index` si cambia.
  go(delta) {
    const next = this.safeIndex + delta;
    if (next < 0 || next >= this.items.length || next === this.safeIndex) return;
    this.setIndex(next);
  }
  setIndex(i7) {
    if (i7 === this.safeIndex) return;
    this.index = i7;
    this.dispatchEvent(
      new CustomEvent("ok-index", { detail: { index: i7 }, bubbles: true, composed: true })
    );
  }
  // Pide cerrar: anima el fade-out y al terminar emite `ok-close` (el consumidor pone `open=false`).
  requestClose() {
    this.unbind();
    this.shown = false;
    const box = this.portalRoot?.querySelector(".lightbox");
    const finish = () => {
      this.dispatchEvent(new CustomEvent("ok-close", { bubbles: true, composed: true }));
    };
    if (box && !this.prefersReducedMotion()) {
      box.addEventListener("transitionend", finish, { once: true });
    } else {
      finish();
    }
  }
  // Nombre de fichero mostrado en la cabecera (alt o último segmento de la URL).
  fileName(item) {
    if (!item) return "";
    if (item.alt) return item.alt;
    try {
      const path = item.src.split(/[?#]/)[0];
      return path.substring(path.lastIndexOf("/") + 1) || item.src;
    } catch {
      return item.src;
    }
  }
  render() {
    return A;
  }
  // Overlay (cabecera + medio + filmstrip). Se renderiza en el portal de `document.body`.
  overlayTemplate() {
    const items = this.items;
    const i7 = this.safeIndex;
    const current = items[i7];
    const isVideo = current?.type === "video";
    const name = this.fileName(current);
    const total = items.length;
    return b2`
      <div
        class="lightbox ${this.shown ? "shown" : ""}"
        role="dialog"
        aria-modal="true"
        aria-label=${name}
      >
        <div class="head">
          <div class="meta">
            <span class="count">${total ? i7 + 1 : 0} / ${total}</span>
            ${name ? b2`<span class="sep">·</span><span>${name}</span>` : null}
          </div>
          <div class="actions">
            ${current ? b2`<a
                  class="icon-btn"
                  href=${current.src}
                  download
                  target="_blank"
                  rel="noopener"
                  aria-label=${this.t.download}
                >
                  <ion-icon .icon=${iconDownloadOutline}></ion-icon>
                </a>` : null}
            ${isCapable() ? b2`<button
                  type="button"
                  class="icon-btn"
                  aria-label=${this.fullscreenOn ? this.t.exitFullscreen : this.t.fullscreen}
                  @click=${() => void this.toggleFullscreen()}
                >
                  <ion-icon
                    .icon=${this.fullscreenOn ? iconContractOutline : iconExpandOutline}
                  ></ion-icon>
                </button>` : null}
            <button
              type="button"
              class="icon-btn"
              aria-label=${this.t.close}
              @click=${() => this.requestClose()}
            >
              <ion-icon .icon=${iconCloseOutline}></ion-icon>
            </button>
          </div>
        </div>

        <div class="main">
          <button
            type="button"
            class="nav prev"
            aria-label=${this.t.prev}
            ?disabled=${i7 <= 0}
            @click=${() => this.go(-1)}
          >
            <ion-icon .icon=${iconChevronBackOutline}></ion-icon>
          </button>

          ${current ? isVideo ? b2`<video
                  class="media"
                  src=${current.src}
                  controls
                  playsinline
                  aria-label=${name}
                ></video>` : b2`<img class="media" src=${current.src} alt=${name} />` : b2`<div class="media-empty"></div>`}

          <button
            type="button"
            class="nav next"
            aria-label=${this.t.next}
            ?disabled=${i7 >= total - 1}
            @click=${() => this.go(1)}
          >
            <ion-icon .icon=${iconChevronForwardOutline}></ion-icon>
          </button>
        </div>

        ${total > 1 ? b2`<div class="strip" role="tablist">
              ${items.map((it, idx) => this.renderThumb(it, idx, idx === i7))}
            </div>` : null}
      </div>
    `;
  }
  renderThumb(item, idx, active) {
    const isVideo = item.type === "video";
    return b2`<button
      type="button"
      class="thumb ok-tap ${active ? "active" : ""}"
      role="tab"
      aria-selected=${active ? "true" : "false"}
      aria-label=${this.fileName(item)}
      @click=${() => this.setIndex(idx)}
    >
      ${isVideo ? b2`<span class="vid"><ion-icon .icon=${iconPlayOutline}></ion-icon></span>` : b2`<img src=${item.thumb ?? item.src} alt="" loading="lazy" />`}
    </button>`;
  }
  /** El `.lightbox` vive en el portal, que tiene shadow root PROPIO: no está en este `shadowRoot`. */
  boxEl() {
    return this.portalRoot?.querySelector(".lightbox") ?? null;
  }
  // Pantalla completa nativa sobre el overlay portado.
  //
  // Pregunta por ESTE overlay, no por «¿hay algo a pantalla completa?»: con el shell del Hub en modo
  // inmersivo la pregunta global era siempre que sí, y el botón cerraba el modo del shell en vez de
  // agrandar la galería. `isActive` mira además el shadow root del portal, porque
  // `document.fullscreenElement` reporta el HOST del portal y nunca el `.lightbox`.
  async toggleFullscreen() {
    const box = this.boxEl();
    if (!box) return;
    try {
      await toggle(box);
    } catch {
    }
  }
};
__decorateClass4([
  n4({ attribute: false })
], OkLightbox.prototype, "items");
__decorateClass4([
  n4({ type: Number })
], OkLightbox.prototype, "index");
__decorateClass4([
  n4({ type: Boolean })
], OkLightbox.prototype, "open");
__decorateClass4([
  n4({ attribute: false })
], OkLightbox.prototype, "labels");
__decorateClass4([
  r5()
], OkLightbox.prototype, "shown");
__decorateClass4([
  r5()
], OkLightbox.prototype, "fullscreenOn");
define("ok-lightbox", OkLightbox);

// @erplora/module-sdk/src/index.ts
function isEmpty(v3) {
  return v3 === null || v3 === void 0 || v3 === "";
}
var ListController = class {
  constructor(client, queryName, onChange2 = () => {
  }, opts = {}) {
    this.client = client;
    this.queryName = queryName;
    this.onChange = onChange2;
    this.rows = [];
    this.total = 0;
    this.loading = false;
    this.error = "";
    /** Descarta respuestas obsoletas si llegan fuera de orden (race de cargas concurrentes). */
    this.seq = 0;
    this.state = {
      page: 0,
      pageSize: opts.pageSize ?? 50,
      search: "",
      sort: opts.sort,
      dir: opts.dir ?? "asc",
      filters: { ...opts.filters ?? {} },
      context: { ...opts.context ?? {} }
    };
  }
  /** Nº de páginas según el total del servidor (mínimo 1). */
  get pageCount() {
    return Math.max(1, Math.ceil(this.total / this.state.pageSize));
  }
  /** (Re)carga la página actual desde el servidor. */
  async load() {
    const s5 = this.state;
    const mySeq = ++this.seq;
    this.loading = true;
    this.error = "";
    this.onChange();
    try {
      const page = await this.client.queryPage(this.queryName, {
        limit: s5.pageSize,
        offset: s5.page * s5.pageSize,
        search: s5.search,
        sort: s5.sort,
        dir: s5.dir,
        filters: s5.filters,
        params: s5.context
      });
      if (mySeq !== this.seq) return;
      this.rows = page.rows ?? [];
      this.total = page.total ?? this.rows.length;
    } catch (e5) {
      if (mySeq !== this.seq) return;
      this.rows = [];
      this.total = 0;
      this.error = e5 instanceof Error ? e5.message : "Error cargando datos";
    } finally {
      if (mySeq === this.seq) {
        this.loading = false;
        this.onChange();
      }
    }
  }
  setPage(page) {
    this.state.page = Math.max(0, page);
    void this.load();
  }
  setSort(sort, dir) {
    this.state.sort = sort;
    this.state.dir = dir;
    this.state.page = 0;
    void this.load();
  }
  setSearch(search) {
    this.state.search = search;
    this.state.page = 0;
    void this.load();
  }
  /** Cambia el nº de filas por página y recarga desde la página 0. */
  setPageSize(pageSize) {
    this.state.pageSize = Math.max(1, pageSize);
    this.state.page = 0;
    void this.load();
  }
  /** Aplica/quita un filtro de columna; valores vacíos lo eliminan. Vuelve a la página 0. */
  setFilter(col, value) {
    if (isEmpty(value)) {
      delete this.state.filters[col];
    } else if (typeof value === "object" && value !== null) {
      const prev = this.state.filters[col] ?? {};
      const merged = { ...prev, ...value };
      const cleaned = Object.fromEntries(Object.entries(merged).filter(([, v3]) => !isEmpty(v3)));
      if (Object.keys(cleaned).length === 0) delete this.state.filters[col];
      else this.state.filters[col] = cleaned;
    } else {
      this.state.filters[col] = value;
    }
    this.state.page = 0;
    void this.load();
  }
  /** Fija/actualiza los params de contexto obligatorios (p.ej. al seleccionar el padre).
   *  Vuelve a la página 0 y recarga. Pasa `{}` o keys con valor vacío para limpiar. */
  setContext(context) {
    this.state.context = { ...context };
    this.state.page = 0;
    void this.load();
  }
  reset() {
    this.state.page = 0;
    this.state.search = "";
    this.state.filters = {};
    void this.load();
  }
};
function createListController(client, queryName, onChange2 = () => {
}, opts = {}) {
  return new ListController(client, queryName, onChange2, opts);
}

// locales/es.json
var es_default = {
  name: "Bandeja de WhatsApp",
  description: "Conversaciones de WhatsApp, plantillas de mensaje y ajustes del canal.",
  navigation: {
    inbox: {
      label: "Bandeja de entrada"
    },
    settings: {
      label: "Ajustes"
    }
  },
  billing: {
    quota: {
      billable_messages_per_month: "mensajes al mes"
    },
    tiers: {
      free: "Gratis",
      basic: "Basic",
      pro: "Pro",
      enterprise: "Enterprise"
    }
  },
  ui: {
    inboxTitle: "Bandeja de WhatsApp",
    templatesTitle: "Plantillas de WhatsApp",
    colContact: "Contacto",
    colPhone: "Tel\xE9fono",
    colStatus: "Estado",
    colUnread: "Sin leer",
    yesterday: "Ayer",
    colLastMessage: "\xDAltimo mensaje",
    colActions: "Acciones",
    colName: "Nombre",
    colLanguage: "Idioma",
    colCategory: "Categor\xEDa",
    colMetaStatus: "Estado en Meta",
    colActive: "Activa",
    colBody: "Cuerpo",
    statusActive: "Activa",
    statusClosed: "Cerrada",
    categoryUtility: "Utility",
    categoryMarketing: "Marketing",
    categoryAuthentication: "Authentication",
    metaPending: "En revisi\xF3n",
    metaApproved: "Aprobada",
    metaRejected: "Rechazada",
    metaNotSent: "Sin enviar a Meta",
    metaPaused: "Pausada por Meta",
    metaDisabled: "Desactivada por Meta",
    metaDeleted: "Borrada en WhatsApp Manager",
    metaActionNotSent: "Meta no ha recibido esta plantilla. Solo puedes usarla para responder dentro de las 24 horas siguientes al \xFAltimo mensaje del cliente.",
    metaActionPending: "Meta la est\xE1 revisando. Suele tardar unos minutos, hasta 24 horas. No la env\xEDes todav\xEDa.",
    metaActionApproved: "Puedes enviarla cuando quieras, tambi\xE9n fuera de la ventana de 24 horas.",
    metaActionRejected: "Meta la ha rechazado. Cambia el texto en WhatsApp Manager y vuelve a enviarla a revisi\xF3n desde ah\xED.",
    metaActionPaused: "Demasiada gente la ha denunciado y Meta no la entregar\xE1 durante un tiempo. Cambia el texto en WhatsApp Manager y vuelve a enviarla desde ah\xED.",
    metaActionDisabled: "Meta no volver\xE1 a aceptar esta plantilla. Escribe otra con un texto distinto.",
    metaActionDeleted: "Meta ya no tiene esta plantilla, as\xED que nada de lo que la use se enviar\xE1. B\xF3rrala aqu\xED, o escribe una nueva con otro nombre.",
    metaActionUnknown: "Consulta esta plantilla en WhatsApp Manager: Meta informa de un estado que esta pantalla a\xFAn no conoce.",
    yes: "S\xED",
    no: "No",
    searchInbox: "Filtrar contacto o tel\xE9fono\u2026",
    searchTemplates: "Buscar nombre o categor\xEDa\u2026",
    emptyInbox: "Sin conversaciones.",
    emptyTemplates: "Sin plantillas.",
    loading: "Cargando\u2026",
    errCreateTemplate: "No se pudo crear la plantilla",
    placeholderName: "Nombre",
    placeholderLanguage: "Idioma (es)",
    placeholderCategory: "Categor\xEDa\u2026",
    placeholderBody: "Cuerpo del mensaje",
    saving: "Guardando\u2026",
    add: "A\xF1adir",
    openConversation: "Abrir",
    closeView: "Cerrar",
    emptyThread: "Esta conversaci\xF3n todav\xEDa no tiene mensajes.",
    unknownDirection: "Mensaje no reconocido",
    attachment: "Adjunto",
    assignedTo: "Asignada a",
    assignPlaceholder: "Id del empleado (vac\xEDo = nadie)",
    assign: "Asignar",
    unassign: "Desasignar",
    errLoadThread: "No se pudo cargar la conversaci\xF3n",
    errAssign: "No se pudo asignar la conversaci\xF3n",
    delete: "Borrar",
    edit: "Editar",
    save: "Guardar",
    cancel: "Cancelar",
    editTemplate: "Editar plantilla",
    errUpdateTemplate: "No se pudo actualizar la plantilla",
    confirmDeleteTemplate: "\xBFBorrar esta plantilla?",
    errDeleteTemplate: "No se pudo borrar la plantilla",
    settingsTitle: "Ajustes del canal",
    helpConnectNeedsNewerHub: "Este hub es demasiado antiguo para conectar el n\xFAmero desde aqu\xED. Actualiza el hub y vuelve a esta pantalla.",
    useAppointmentsName: "Reservar citas",
    useAppointmentsSummary: "Una clienta pide cita por WhatsApp, el asistente le ofrece las horas que de verdad tienes libres y le reserva la que elija; luego le dice que ya est\xE1, y le avisa cuando t\xFA confirmas su cita.",
    usesGoToApps: "Ver aplicaciones",
    stepNumber: "Tu n\xFAmero",
    stepUses: "\xBFPara qu\xE9 lo usas?",
    helpConnectScanQr: "Escanea el c\xF3digo QR con la app WhatsApp Business del n\xFAmero del negocio. Sigues usando WhatsApp en el m\xF3vil como siempre.",
    activate: "Activar",
    notNow: "Ahora no",
    turnOff: "Desactivar",
    stateOn: "Activo",
    stateOff: "Desactivada",
    policyReview: "Las reviso yo antes",
    useAppointmentsPolicyAuto: "Las citas se confirman solas",
    useAppointmentsPolicyReviewHelp: "Cada cita nueva te espera en la Agenda con \u201CConfirmar\u201D; a la clienta le decimos que se la confirmas en breve.",
    useAppointmentsPolicyError: "No se pudo guardar c\xF3mo se confirman las citas. Int\xE9ntalo otra vez.",
    advancedInAutomations: "Ajustes avanzados en Automatizaciones",
    advancedMetaTemplates: "Plantillas de Meta",
    usesNeedsNewerHub: "Este hub es demasiado antiguo para activarlo desde aqu\xED. Actualiza el hub.",
    usesNeedBookingModule: "Instala Citas o Reservas para que WhatsApp reserve solo",
    usesNeedNewerBookingModule: "Actualiza Citas o Reservas para que WhatsApp reserve solo",
    usesNeedMissingModule: "\xAB{use}\xBB necesita la aplicaci\xF3n {module}, y no est\xE1 instalada. Inst\xE1lala desde Aplicaciones.",
    usesNeedPausedModule: "\xAB{use}\xBB necesita la aplicaci\xF3n {module}, y est\xE1 en pausa. React\xEDvala en Aplicaciones.",
    usesNeedUpdatedModule: "\xAB{use}\xBB necesita la aplicaci\xF3n {module} en la versi\xF3n {floor} o posterior, y este hub tiene la {installed}. Actual\xEDzala en Aplicaciones.",
    neighbourAppointments: "Citas",
    neighbourCustomers: "Clientes",
    neighbourReservations: "Reservas",
    neighbourServices: "Servicios",
    neighbourStaff: "Personal",
    activateForbidden: "Solo un due\xF1o o un administrador puede activarlo.",
    errActivate: "No se pudo activar. No se ha cambiado nada: int\xE9ntalo otra vez.",
    errTemplates: "No hemos podido saber qu\xE9 hay activo ahora mismo. Vuelve a cargar la pantalla.",
    useAppointmentsConsent: "WhatsApp contestar\xE1 solo: lee tu agenda, ofrece los huecos libres, reserva, mueve o anula la cita de la clienta que escribe y le contesta; y le avisa cuando confirmas su cita. No puede tocar las citas de nadie m\xE1s. \xBFLo activas?",
    useAppointmentsDone: "Listo. Escr\xEDbete desde otro m\xF3vil: \u201Cquiero cita ma\xF1ana\u201D.",
    useReservationsName: "Reservar mesa",
    useReservationsSummary: "Un cliente pide mesa por WhatsApp, el asistente le ofrece las horas que de verdad tienes libres y le reserva la que elija; luego le dice que ya est\xE1.",
    useReservationsConsent: "WhatsApp contestar\xE1 solo: mira las mesas libres, reserva la mesa de quien escribe y le contesta. \xBFLo activas?",
    useReservationsDone: "Listo. Escr\xEDbete desde otro m\xF3vil: \u201Cquiero mesa para dos ma\xF1ana\u201D.",
    useReservationsPolicyAuto: "Las reservas se confirman solas",
    useReservationsPolicyReviewHelp: "Cada reserva nueva te espera en Reservas con \u201CConfirmar\u201D; al cliente le decimos que se la confirmas en breve.",
    useReservationsPolicyError: "No se pudo guardar c\xF3mo se confirman las reservas. Int\xE9ntalo otra vez.",
    doorRefusalUnknown: "No se ha podido registrar la plantilla en Meta, y el motivo es uno que esta pantalla a\xFAn no conoce ({code}). Queda guardada aqu\xED: busca ese c\xF3digo en WhatsApp Manager o envi\xE1selo a soporte.",
    doorRefusalNoCode: "No se ha podido registrar la plantilla en Meta. Queda guardada aqu\xED: prueba a guardarla otra vez dentro de un rato.",
    metaRejectedReason: "Motivo de Meta: {reason}",
    metaSyncUnavailable: "No hemos podido comprobar con Meta si hay veredictos nuevos, as\xED que lo que ves es lo \xFAltimo que sabemos. Vuelve a abrir esta pesta\xF1a dentro de un rato.",
    headerMediaImage: "Cabecera con imagen: la imagen se elige al enviar el mensaje.",
    headerMediaVideo: "Cabecera con v\xEDdeo: el v\xEDdeo se elige al enviar el mensaje.",
    headerMediaDocument: "Cabecera con documento: el documento se elige al enviar el mensaje.",
    templateButtons: "Botones",
    buttonQuickReply: "Respuesta r\xE1pida",
    buttonUrl: "Abre un enlace",
    buttonPhone: "Llama al n\xFAmero",
    templateManagedInMeta: "Esta plantilla lleva una imagen, v\xEDdeo o documento en la cabecera, o un bot\xF3n de enlace con variable, as\xED que su texto se cambia en WhatsApp Manager. Al volver a abrir esta pesta\xF1a ver\xE1s lo que diga Meta.",
    metaOnlyTemplates: "Estas plantillas de WhatsApp Manager todav\xEDa no se pueden traer a esta lista (llevan un carrusel, una oferta por tiempo limitado, un bot\xF3n de copiar c\xF3digo o de WhatsApp Flow, una ubicaci\xF3n en la cabecera o una variable en la cabecera). Gesti\xF3nalas en WhatsApp Manager: {names}",
    doorRefusal: {
      invalid_name: "Meta no ha aceptado el nombre. Usa solo min\xFAsculas, n\xFAmeros y guiones bajos \u2014sin espacios ni acentos\u2014 y vuelve a intentarlo.",
      invalid_category: "Meta no ha aceptado la categor\xEDa. Elige Utilidad, Marketing o Autenticaci\xF3n y vuelve a enviarla.",
      invalid_language: "Meta no ha aceptado el idioma. Escr\xEDbelo como c\xF3digo de idioma de Meta, por ejemplo es o en_US.",
      invalid_placeholders: "Meta no ha aceptado los huecos del cuerpo. Num\xE9ralos en orden, empezando por {{1}} y sin saltarte ninguno.",
      invalid_header_placeholders: "Meta no ha aceptado el encabezado: admite un hueco como mucho, y tiene que ser {{1}}.",
      mixed_placeholders: "El cuerpo mezcla variables numeradas ({{1}}) y con nombre ({{nombre}}). Meta admite un solo tipo por plantilla: usa solo uno de los dos.",
      invalid_named_placeholders: "Meta no ha aceptado el nombre de una variable del cuerpo. Usa solo min\xFAsculas, n\xFAmeros y guiones bajos, sin espacios, como {{nombre_cliente}}.",
      invalid_variables: "Meta no ha aceptado la lista de variables. Pon un nombre por cada hueco que uses en el texto.",
      missing_body: "Meta no revisa una plantilla vac\xEDa. Escribe el mensaje que va a leer el cliente.",
      missing_example: "Meta necesita un ejemplo para cada hueco. Rellena qu\xE9 vale cada uno en un mensaje real.",
      no_whatsapp_number: "Este negocio todav\xEDa no tiene un n\xFAmero de WhatsApp conectado. Con\xE9ctalo en Ajustes y vuelve a enviar la plantilla.",
      template_not_found: "Meta ya no tiene esta plantilla. Gu\xE1rdala otra vez para volver a enviarla a revisi\xF3n.",
      meta_rate_limited: "Meta est\xE1 rechazando peticiones ahora mismo. La plantilla no tiene nada mal: espera unos minutos y vuelve a guardarla.",
      meta_permission_denied: "Meta no deja a este negocio gestionar plantillas. Comprueba en WhatsApp Manager que la cuenta sigue conectada y con permiso.",
      meta_unreachable: "Meta no ha contestado. La plantilla queda guardada aqu\xED; vuelve a guardarla dentro de un rato para enviarla a revisi\xF3n.",
      meta_template_failed: "Meta ha rechazado la plantilla sin decir por qu\xE9. Rev\xEDsala en WhatsApp Manager, donde s\xED viene el motivo.",
      cloud_rejected: "erplora.com no ha querido registrar la plantilla. Queda guardada aqu\xED: int\xE9ntalo otra vez y avisa a soporte si sigue pasando.",
      cloud_unreachable: "Esta caja no ha podido conectar con erplora.com. La plantilla queda guardada aqu\xED; revisa la conexi\xF3n a internet y vuelve a guardarla para enviarla a revisi\xF3n.",
      cloud_unreadable: "erplora.com ha contestado algo que esta caja no ha sabido leer. La plantilla queda guardada aqu\xED: int\xE9ntalo dentro de un rato.",
      hub_not_enrolled: "Esta caja todav\xEDa no est\xE1 emparejada con erplora.com, as\xED que no puede enviar plantillas a Meta. Avisa a soporte.",
      capability_denied: "WhatsApp no tiene permiso para enviar mensajes desde este hub. Conc\xE9deselo en Ajustes \u2192 Permisos y vuelve a guardar la plantilla.",
      invalid_buttons: "Meta no ha aceptado los botones. Cada uno tiene que ser una respuesta r\xE1pida, un enlace o una llamada: rev\xEDsalos y vuelve a guardar.",
      invalid_button_text: "Meta no ha aceptado un bot\xF3n: todos necesitan un texto de 25 caracteres como mucho.",
      invalid_button_url: "Meta no ha aceptado un bot\xF3n de enlace. Escribe la direcci\xF3n completa, empezando por https://, y sin variables tipo {{1}}.",
      invalid_button_phone: "Meta no ha aceptado un bot\xF3n de llamada. Escribe el n\xFAmero con su prefijo de pa\xEDs, por ejemplo +34600111222.",
      too_many_buttons: "Meta no ha aceptado los botones: una plantilla lleva 10 como mucho, y no m\xE1s de 2 enlaces y 1 bot\xF3n de llamada.",
      buttons_not_grouped: "Meta no ha aceptado el orden de los botones: las respuestas r\xE1pidas van juntas, y los enlaces y llamadas, juntos.",
      buttons_not_allowed_for_category: "Las plantillas de autenticaci\xF3n no pueden llevar botones desde aqu\xED. Quita los botones o elige otra categor\xEDa."
    },
    mediaKind: {
      image: "Foto",
      sticker: "Sticker",
      audio: "Nota de voz",
      video: "V\xEDdeo",
      document: "Documento"
    },
    mediaLoading: "Cargando el adjunto\u2026",
    mediaError: "No se ha podido cargar el adjunto.",
    mediaRetry: "Reintentar",
    mediaUnavailable: "Este adjunto a\xFAn no se puede ver aqu\xED: lo tienes en el WhatsApp de tu m\xF3vil.",
    mediaPlay: "Reproducir",
    mediaDownload: "Descargar",
    mediaOpen: "Abrir",
    mediaCannotPlay: "Este dispositivo no puede reproducirlo: desc\xE1rgalo y \xE1brelo con otra aplicaci\xF3n.",
    threadRepliesElsewhere: "Desde esta pantalla no se contesta: responde desde el WhatsApp de tu m\xF3vil o deja que conteste una automatizaci\xF3n.",
    viewerOpen: "Ver la foto en grande",
    viewerPrev: "Foto anterior",
    viewerNext: "Foto siguiente",
    viewerClose: "Cerrar",
    viewerDownload: "Descargar",
    viewerFullscreen: "Pantalla completa",
    viewerExitFullscreen: "Salir de pantalla completa",
    buttonsHint: "Opcional. Hasta 10 botones: respuestas r\xE1pidas, hasta 2 enlaces y 1 bot\xF3n de llamada. Las respuestas r\xE1pidas se mantienen juntas.",
    buttonType: "Tipo de bot\xF3n",
    buttonText: "Texto del bot\xF3n",
    buttonUrlField: "Enlace (https://\u2026)",
    buttonPhoneField: "Tel\xE9fono con prefijo de pa\xEDs",
    addButton: "A\xF1adir bot\xF3n",
    removeButton: "Quitar bot\xF3n"
  },
  errors: {
    "whatsapp_inbox.conversation_not_found": "Esa conversaci\xF3n no existe en este negocio.",
    "whatsapp_inbox.template_already_here": "Este negocio ya tiene una plantilla con ese nombre e idioma (viva o borrada aqu\xED), as\xED que no se ha tra\xEDdo nada.",
    "whatsapp_inbox.template_not_found": "Esa plantilla no existe en este negocio."
  }
};

// locales/en.json
var en_default = {
  name: "WhatsApp Inbox",
  navigation: {
    inbox: {
      label: "Inbox"
    },
    settings: {
      label: "Settings"
    }
  },
  billing: {
    quota: {
      billable_messages_per_month: "messages per month"
    },
    tiers: {
      free: "Free",
      basic: "Basic",
      pro: "Pro",
      enterprise: "Enterprise"
    }
  },
  ui: {
    inboxTitle: "WhatsApp Inbox",
    templatesTitle: "WhatsApp Templates",
    colContact: "Contact",
    colPhone: "Phone",
    colStatus: "Status",
    colUnread: "Unread",
    yesterday: "Yesterday",
    colLastMessage: "Last message",
    colActions: "Actions",
    colName: "Name",
    colLanguage: "Language",
    colCategory: "Category",
    colMetaStatus: "Meta status",
    colActive: "Active",
    colBody: "Body",
    statusActive: "Active",
    statusClosed: "Closed",
    categoryUtility: "Utility",
    categoryMarketing: "Marketing",
    categoryAuthentication: "Authentication",
    metaPending: "In review",
    metaApproved: "Approved",
    metaRejected: "Rejected",
    metaNotSent: "Not sent to Meta",
    metaPaused: "Paused by Meta",
    metaDisabled: "Disabled by Meta",
    metaDeleted: "Deleted in WhatsApp Manager",
    metaActionNotSent: "Meta has not received this template. You can only use it to reply within 24 hours of the customer's last message.",
    metaActionPending: "Meta is reviewing it. It usually takes a few minutes, up to 24 hours. Do not send it yet.",
    metaActionApproved: "You can send it whenever you want, also outside the 24-hour window.",
    metaActionRejected: "Meta turned it down. Change the wording in WhatsApp Manager and send it back for review from there.",
    metaActionPaused: "Too many people reported it, so Meta will not deliver it for a while. Change the wording in WhatsApp Manager and send it back from there.",
    metaActionDisabled: "Meta will not accept this template again. Write a new one with different wording.",
    metaActionDeleted: "Meta no longer has this template, so nothing that uses it will be sent. Delete it here, or write a new one with a different name.",
    metaActionUnknown: "Check this template in WhatsApp Manager: Meta reports a status this screen does not know yet.",
    yes: "Yes",
    no: "No",
    searchInbox: "Filter contact or phone\u2026",
    searchTemplates: "Search name or category\u2026",
    emptyInbox: "No conversations.",
    emptyTemplates: "No templates.",
    loading: "Loading\u2026",
    errCreateTemplate: "Could not create template",
    placeholderName: "Name",
    placeholderLanguage: "Language (es)",
    placeholderCategory: "Category\u2026",
    placeholderBody: "Message body",
    saving: "Saving\u2026",
    add: "Add",
    openConversation: "Open",
    closeView: "Close",
    emptyThread: "No messages in this conversation yet.",
    unknownDirection: "Unrecognised message",
    attachment: "Attachment",
    assignedTo: "Assigned to",
    assignPlaceholder: "Employee id (empty = nobody)",
    assign: "Assign",
    unassign: "Unassign",
    errLoadThread: "Could not load the conversation",
    errAssign: "Could not assign the conversation",
    delete: "Delete",
    edit: "Edit",
    save: "Save",
    cancel: "Cancel",
    editTemplate: "Edit template",
    errUpdateTemplate: "Could not update the template",
    confirmDeleteTemplate: "Delete this template?",
    errDeleteTemplate: "Could not delete the template",
    settingsTitle: "Channel settings",
    helpConnectNeedsNewerHub: "This hub is too old to connect the number from here. Update the hub and come back to this screen.",
    useAppointmentsName: "Book appointments",
    useAppointmentsSummary: "A customer asks for an appointment on WhatsApp, the assistant offers the hours you actually have free, and books the one they pick \u2014 then tells them it is done, and tells them when you confirm their appointment.",
    usesGoToApps: "See apps",
    stepNumber: "Your number",
    stepUses: "What do you use it for?",
    helpConnectScanQr: "Scan the QR code with the WhatsApp Business app of your business number. You keep using WhatsApp on your phone as always.",
    activate: "Turn it on",
    notNow: "Not now",
    turnOff: "Turn off",
    stateOn: "On",
    stateOff: "Off",
    policyReview: "I review them first",
    useAppointmentsPolicyAuto: "Bookings are confirmed automatically",
    useAppointmentsPolicyReviewHelp: "Each new booking waits for you in the Diary with \u201CConfirm\u201D; the customer is told you will confirm shortly.",
    useAppointmentsPolicyError: "We could not save how appointments are confirmed. Try again.",
    advancedInAutomations: "Advanced settings in Automations",
    advancedMetaTemplates: "Meta templates",
    usesNeedsNewerHub: "This hub is too old to turn this on from here. Update the hub.",
    usesNeedBookingModule: "Install Appointments or Reservations so WhatsApp can book on its own",
    usesNeedNewerBookingModule: "Update Appointments or Reservations so WhatsApp can book on its own",
    usesNeedMissingModule: "\u201C{use}\u201D needs the {module} app, and it is not installed. Install it from Apps.",
    usesNeedPausedModule: "\u201C{use}\u201D needs the {module} app, and it is paused. Turn it back on in Apps.",
    usesNeedUpdatedModule: "\u201C{use}\u201D needs the {module} app at version {floor} or later, and this hub has {installed}. Update it in Apps.",
    neighbourAppointments: "Appointments",
    neighbourCustomers: "Customers",
    neighbourReservations: "Reservations",
    neighbourServices: "Services",
    neighbourStaff: "Staff",
    activateForbidden: "Only an owner or an administrator can turn this on.",
    errActivate: "It could not be turned on. Nothing was changed \u2014 try again.",
    errTemplates: "We could not find out what is already turned on. Reload the screen.",
    useAppointmentsConsent: "WhatsApp will answer on its own: it reads your diary, offers free slots, books, moves or cancels the appointment of the customer who writes, and replies to them; and it tells them when you confirm their appointment. It cannot touch anyone else\u2019s appointments. Turn it on?",
    useAppointmentsDone: "Done. Text your number from another phone: \u201CI\u2019d like an appointment tomorrow\u201D.",
    useReservationsName: "Book a table",
    useReservationsSummary: "A guest asks for a table on WhatsApp, the assistant checks the times you really have free, and books the one they pick \u2014 then tells them it is done.",
    useReservationsConsent: "WhatsApp will answer on its own: it checks free tables, books a table for whoever writes, and replies to them. Turn it on?",
    useReservationsDone: "Done. Text your number from another phone: \u201CI\u2019d like a table for two tomorrow\u201D.",
    useReservationsPolicyAuto: "Bookings are confirmed automatically",
    useReservationsPolicyReviewHelp: "Each new booking waits for you in Reservations with \u201CConfirm\u201D; the guest is told you will confirm shortly.",
    useReservationsPolicyError: "We could not save how table bookings are confirmed. Try again.",
    doorRefusalUnknown: "The template could not be registered with Meta, and the reason is one this screen does not know yet ({code}). It is saved here: look that code up in WhatsApp Manager or send it to support.",
    doorRefusalNoCode: "The template could not be registered with Meta. It is saved here: try saving it again in a moment.",
    metaRejectedReason: "Meta's reason: {reason}",
    metaSyncUnavailable: "We could not check with Meta for new verdicts, so what you see is the last we know. Open this tab again in a while.",
    headerMediaImage: "Image header: the image is chosen when the message is sent.",
    headerMediaVideo: "Video header: the video is chosen when the message is sent.",
    headerMediaDocument: "Document header: the document is chosen when the message is sent.",
    templateButtons: "Buttons",
    buttonQuickReply: "Quick reply",
    buttonUrl: "Opens a link",
    buttonPhone: "Calls the number",
    templateManagedInMeta: "This template has an image, video or document header, or a link button with a variable, so its wording is changed in WhatsApp Manager. Open this tab again to see what Meta says.",
    metaOnlyTemplates: "These WhatsApp Manager templates cannot be brought into this list yet (they use a carousel, a limited-time offer, a copy-code or WhatsApp Flow button, a location header, or a variable in the header). Manage them in WhatsApp Manager: {names}",
    doorRefusal: {
      invalid_name: "Meta did not accept the name. Use lowercase letters, numbers and underscores only \u2014 no spaces or accents \u2014 and try again.",
      invalid_category: "Meta did not accept the category. Pick Utility, Marketing or Authentication and send it again.",
      invalid_language: "Meta did not accept the language. Write it as a Meta language code, such as es or en_US.",
      invalid_placeholders: "Meta did not accept the placeholders in the body. Number them in order, starting at {{1}} and with no gaps.",
      invalid_header_placeholders: "Meta did not accept the header: it takes at most one placeholder, and it has to be {{1}}.",
      mixed_placeholders: "The body mixes numbered variables ({{1}}) with named ones ({{name}}). Meta takes one kind per template: use only one of them.",
      invalid_named_placeholders: "Meta did not accept a variable name in the body. Use lowercase letters, digits and underscores only, with no spaces, such as {{first_name}}.",
      invalid_variables: "Meta did not accept the list of variables. Give one name per placeholder used in the text.",
      missing_body: "Meta will not review an empty template. Write the message the customer is going to read.",
      missing_example: "Meta needs an example for every placeholder. Fill in what each one is worth in a real message.",
      no_whatsapp_number: "This business has no WhatsApp number connected yet. Connect it in Settings and send the template again.",
      template_not_found: "Meta no longer has this template. Save it again to send it back for review.",
      meta_rate_limited: "Meta is turning away requests for the moment. Nothing is wrong with the template: wait a few minutes and save it again.",
      meta_permission_denied: "Meta will not let this business manage templates. Check in WhatsApp Manager that the account is still connected and has permission.",
      meta_unreachable: "Meta did not answer. The template is saved here; save it again in a moment to send it for review.",
      meta_template_failed: "Meta turned the template down without saying why. Review it in WhatsApp Manager, where the reason is spelled out.",
      cloud_rejected: "erplora.com refused to register the template. It is saved here: try again, and contact support if it keeps happening.",
      cloud_unreachable: "This till could not reach erplora.com. The template is saved here; check the internet connection and save it again to send it for review.",
      cloud_unreadable: "erplora.com answered something this till could not read. The template is saved here \u2014 try again in a moment.",
      hub_not_enrolled: "This till is not yet paired with erplora.com, so it cannot send templates to Meta. Contact support.",
      capability_denied: "WhatsApp Inbox is not allowed to send WhatsApp messages on this hub. Grant it in Settings \u2192 Permissions and save the template again.",
      invalid_buttons: "Meta did not accept the buttons. Each one has to be a quick reply, a link or a call \u2014 check them and save again.",
      invalid_button_text: "Meta did not accept a button: every button needs a label of up to 25 characters.",
      invalid_button_url: "Meta did not accept a link button. Write the full address, starting with https://, and without {{1}}-style variables.",
      invalid_button_phone: "Meta did not accept a call button. Write the number with its country code, for example +34600111222.",
      too_many_buttons: "Meta did not accept the buttons: a template takes at most 10, with no more than 2 links and 1 call button.",
      buttons_not_grouped: "Meta did not accept the order of the buttons: quick replies go together, and links and calls go together.",
      buttons_not_allowed_for_category: "Authentication templates cannot carry buttons from here. Remove the buttons or choose another category."
    },
    mediaKind: {
      image: "Photo",
      sticker: "Sticker",
      audio: "Voice note",
      video: "Video",
      document: "Document"
    },
    mediaLoading: "Loading attachment\u2026",
    mediaError: "Could not load the attachment.",
    mediaRetry: "Try again",
    mediaUnavailable: "This attachment cannot be shown here yet: you can see it on your phone's WhatsApp.",
    mediaPlay: "Play",
    mediaDownload: "Download",
    mediaOpen: "Open",
    mediaCannotPlay: "This device cannot play it: download it and open it with another app.",
    threadRepliesElsewhere: "Replies are not sent from this screen: answer from WhatsApp on your phone, or let an automation reply.",
    viewerOpen: "See the photo large",
    viewerPrev: "Previous photo",
    viewerNext: "Next photo",
    viewerClose: "Close",
    viewerDownload: "Download",
    viewerFullscreen: "Full screen",
    viewerExitFullscreen: "Exit full screen",
    buttonsHint: "Optional. Up to 10 buttons: quick replies, up to 2 links and 1 call button. Quick replies are kept together.",
    buttonType: "Button type",
    buttonText: "Button text",
    buttonUrlField: "Link (https://\u2026)",
    buttonPhoneField: "Phone number with country code",
    addButton: "Add button",
    removeButton: "Remove button"
  },
  errors: {
    "whatsapp_inbox.conversation_not_found": "That conversation does not exist in this business.",
    "whatsapp_inbox.template_already_here": "This business already holds a template with that name and language (live or deleted here), so nothing was brought in.",
    "whatsapp_inbox.template_not_found": "That template does not exist in this business."
  }
};

// ui/lib/domain-error-text.ts
var SOURCE_LANG = "en";
function textFor(catalog, lang, code) {
  const dict = catalog[lang];
  const text3 = dict?.errors?.[code];
  return typeof text3 === "string" && text3.trim() ? text3 : "";
}
function alreadySpoken(catalog, code, message) {
  if (!message) return false;
  for (const lang of Object.keys(catalog)) {
    const template = textFor(catalog, lang, code);
    const at = template.indexOf("{message}");
    if (at < 0) continue;
    const head = template.slice(0, at);
    const tail = template.slice(at + "{message}".length);
    if (message.length >= head.length + tail.length && message.startsWith(head) && message.endsWith(tail)) return true;
  }
  return false;
}
function domainErrorText(catalog, locale, e5) {
  const code = e5?.code;
  if (typeof code !== "string" || !code) return "";
  const text3 = textFor(catalog, locale, code) || textFor(catalog, SOURCE_LANG, code);
  if (!text3.includes("{message}")) return text3;
  const message = e5 instanceof Error ? e5.message : "";
  if (alreadySpoken(catalog, code, message)) return message;
  return text3.replaceAll("{message}", message);
}

// ui/lib/message-time.ts
function businessTimezone() {
  const tz = globalThis.erplora?.timezone;
  return typeof tz === "string" && tz.trim() ? tz.trim() : "UTC";
}
function usableZone(timezone) {
  try {
    new Intl.DateTimeFormat("en", { timeZone: timezone });
    return timezone;
  } catch {
    return "UTC";
  }
}
function businessDay(instant, timezone) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).format(instant);
}
function previousDay(day) {
  const [y3, m4, d3] = day.split("-").map(Number);
  return new Date(Date.UTC(y3, m4 - 1, d3 - 1)).toISOString().slice(0, 10);
}
function formatMessageTime(value, opts) {
  const raw = value == null ? "" : String(value);
  if (!raw) return "";
  const instant = new Date(raw);
  if (Number.isNaN(instant.getTime())) return raw;
  const timeZone = usableZone(opts.timezone);
  const locale = opts.locale || "es";
  let time;
  let date;
  try {
    time = instant.toLocaleTimeString(locale, { timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
    date = instant.toLocaleDateString(locale, { timeZone, day: "2-digit", month: "2-digit", year: "numeric" });
  } catch {
    return raw;
  }
  const day = businessDay(instant, timeZone);
  const today = businessDay(opts.now ?? /* @__PURE__ */ new Date(), timeZone);
  if (day === today) return time;
  const label = day === previousDay(today) ? opts.yesterday : date;
  return opts.withTime ? `${label}, ${time}` : label;
}

// ui/lib/message-media.ts
var KINDS = ["image", "sticker", "audio", "video", "document"];
function isKind(value) {
  return typeof value === "string" && KINDS.includes(value);
}
function asObject(value) {
  if (typeof value === "string") {
    if (!value) return null;
    try {
      return asObject(JSON.parse(value));
    } catch {
      return null;
    }
  }
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}
var text = (value) => typeof value === "string" ? value : "";
function messageMedia(m4) {
  if (!isKind(m4.message_type)) return null;
  const asset = asObject(asObject(m4.extra_metadata)?.[m4.message_type]);
  const mediaId = text(asset?.id);
  if (!asset || !mediaId) return null;
  return {
    kind: m4.message_type,
    mediaId,
    mimeType: text(asset.mime_type),
    caption: text(asset.caption),
    filename: text(asset.filename)
  };
}
var EXTENSIONS = {
  "audio/ogg": "ogg",
  "audio/opus": "opus",
  "audio/mpeg": "mp3",
  "audio/mp4": "m4a",
  "audio/aac": "aac",
  "audio/amr": "amr",
  "video/mp4": "mp4",
  "video/3gpp": "3gp"
};
function mediaFileName(media, label) {
  if (media.filename) return media.filename;
  const extension = EXTENSIONS[media.mimeType.split(";")[0].trim().toLowerCase()];
  return extension ? `${label}.${extension}` : label;
}

// ui/components/erp-whatsapp-inbox-inbox/erp-whatsapp-inbox-inbox.ts
var CATALOG = { es: es_default, en: en_default };
var SHOWN_INLINE = /* @__PURE__ */ new Set(["image", "sticker"]);
function devicePlays(media) {
  if (!media.mimeType) return true;
  const probe = document.createElement(media.kind === "video" ? "video" : "audio");
  return probe.canPlayType(media.mimeType) !== "";
}
var VIEWER_LABELS = {
  prev: "ui.viewerPrev",
  next: "ui.viewerNext",
  close: "ui.viewerClose",
  download: "ui.viewerDownload",
  fullscreen: "ui.viewerFullscreen",
  exitFullscreen: "ui.viewerExitFullscreen"
};
var THREAD_PAGE = 200;
var STATUS_KEYS = { active: "ui.statusActive", closed: "ui.statusClosed" };
function erplora() {
  const c5 = globalThis.erplora;
  if (!c5) throw new Error("erplora SDK no inicializado por el shell");
  return c5;
}
function whenText(value, withTime = false) {
  const client = erplora();
  return formatMessageTime(value, {
    locale: client.locale,
    timezone: businessTimezone(),
    yesterday: client.t(CATALOG, "ui.yesterday"),
    withTime
  });
}
function mediaDoor() {
  const client = erplora();
  if (typeof client.forModule !== "function") return null;
  const door2 = client.forModule("whatsapp_inbox")?.whatsappMedia;
  return door2 && typeof door2.get === "function" ? door2 : null;
}
function can(permission) {
  const client = erplora();
  return typeof client.hasPermission === "function" ? client.hasPermission(permission) : true;
}
function domainErrorText2(e5, fallbackKey) {
  const declared = domainErrorText(CATALOG, erplora().locale, e5);
  if (declared) return declared;
  return (e5 instanceof Error ? e5.message : "") || erplora().t(CATALOG, fallbackKey);
}
var ErpWhatsappInboxInbox = class extends i3 {
  constructor() {
    super(...arguments);
    this.tick = 0;
    this.detail = null;
    this.messages = [];
    this.detailError = "";
    this.detailBusy = false;
    this.media = {};
    this.unplayable = /* @__PURE__ */ new Set();
    this.viewing = null;
    this.assignTo = "";
    this.onLocaleChange = () => this.requestUpdate();
  }
  static {
    this.styles = i`
    :host { display:flex; flex-direction:column; height:100%; min-height:0; font-family: system-ui, sans-serif; color: var(--ion-text-color, #1c1b18); }
    .page { display:flex; flex-direction:column; min-height:0; flex:1 1 auto; }
    .page > ok-data-table { flex:1 1 auto; min-height:0; }
    header { display:flex; gap:.5rem; align-items:center; margin-bottom:.75rem; }
    h2 { margin:0; font-size:1.15rem; flex:1; }
    .err { color:#d9480f; font-weight:600; }
    .unread { color:#1971c2; font-weight:700; }
    /* The thread lives ABOVE the list and scrolls on its own, so a long conversation never pushes
       the table footer off the screen. Same shape as the tickets detail. */
    .detail { flex:0 1 auto; overflow:auto; border:1px solid var(--ion-border-color,#e7e2d6);
      border-radius:12px; padding:1rem; margin:0 0 1rem; background:var(--ion-card-background,#fffdf7); }
    .detail-head { display:flex; gap:.6rem; align-items:center; flex-wrap:wrap; margin-bottom:.5rem; }
    .detail-head h3 { margin:0; font-size:1.05rem; }
    .detail-head .phone { color:var(--ion-color-medium,#6f6a5e); }
    .detail-head .spacer { flex:1; }
    .thread { display:flex; flex-direction:column; gap:.4rem; margin:.6rem 0; }
    .msg { max-width:min(38rem, 85%); padding:.45rem .7rem; border-radius:12px;
      background:var(--ok-surface-2, var(--ion-color-step-50, rgba(0,0,0,.04))); }
    .msg.inbound { align-self:flex-start; }
    .msg.outbound { align-self:flex-end; background:var(--ion-color-primary-tint, #d0ebff); }
    /* Neither side: centred and outlined so it reads as «we do not know who said this», never as
       one more customer message (whatsapp_inbox#66). */
    .msg.unknown { align-self:center; text-align:center;
      border:1px dashed var(--ion-color-warning-shade, #b8860b); background:transparent; }
    .msg .body { white-space:pre-wrap; margin:0; }
    .msg .when { display:block; font-size:.75rem; color:var(--ion-color-medium,#6f6a5e); margin-top:.15rem; }
    .msg .kind { font-size:.75rem; font-weight:600; color:var(--ion-color-medium,#6f6a5e); }
    .msg .media { display:flex; flex-direction:column; gap:.3rem; margin:.2rem 0; }
    .msg .media img { display:block; max-width:100%; max-height:16rem; border-radius:8px; object-fit:contain; }
    .msg .media .open-photo { display:block; padding:0; border:0; background:none; cursor:zoom-in; max-width:100%; }
    .msg .media audio, .msg .media video { max-width:100%; }
    .msg .media video { max-height:20rem; border-radius:8px; }
    .msg .media a { color:var(--ion-color-primary,#1971c2); font-weight:600; word-break:break-all; }
    .msg .media .note, .msg .media .err { margin:0; }
    .empty { color:var(--ion-color-medium,#6f6a5e); }
    .assign { display:flex; gap:.5rem; align-items:end; flex-wrap:wrap; margin-top:.75rem; }
    .note { font-size:.85rem; color:var(--ion-color-medium,#6f6a5e); margin:.5rem 0 0; }
    /* 44px minimum touch target: this screen is used one-handed, at a counter. */
    ion-button { --min-height: 44px; }
  `;
  }
  get rowActions() {
    return [
      { id: "open", label: erplora().t(CATALOG, "ui.openConversation"), icon: "open-outline", color: "primary" }
    ];
  }
  get columns() {
    const t5 = (k2) => erplora().t(CATALOG, k2);
    return [
      { key: "contact_name", header: t5("ui.colContact"), sortable: true, filterable: true, filterType: "text" },
      { key: "contact_phone", header: t5("ui.colPhone"), sortable: true, filterable: true, filterType: "text" },
      {
        key: "status",
        header: t5("ui.colStatus"),
        sortable: true,
        filterable: true,
        filterType: "select",
        options: Object.entries(STATUS_KEYS).map(([value, key]) => ({ value, label: t5(key) })),
        // The cell names the status like the filter does (whatsapp_inbox#189); an unlearned value is
        // shown as it arrived rather than disguised as another status.
        format: (r6) => {
          const key = STATUS_KEYS[String(r6.status ?? "")];
          return key ? t5(key) : String(r6.status ?? "");
        }
      },
      {
        key: "unread_count",
        header: t5("ui.colUnread"),
        align: "right",
        sortable: true,
        filterable: true,
        filterType: "range",
        format: (r6) => Number(r6.unread_count) > 0 ? String(r6.unread_count) : "\u2014"
      },
      {
        key: "last_message_at",
        header: t5("ui.colLastMessage"),
        sortable: true,
        filterable: true,
        filterType: "daterange",
        // Sorting and the date-range filter go to the server on the raw instant; this is display only.
        format: (r6) => whenText(r6.last_message_at)
      }
    ];
  }
  // TODO-LIT: componentWillLoad → connectedCallback. Recuerda: connectedCallback se dispara
  // en CADA reconexión al DOM (no solo en el primer montaje). Si la init debe correr una
  // sola vez tras el primer render, considera firstUpdated() en su lugar.
  async connectedCallback() {
    super.connectedCallback();
    window.addEventListener("erplora:locale-changed", this.onLocaleChange);
    this.ctrl = createListController(erplora(), "whatsapp_inbox.conversations.list", () => this.requestUpdate(), {
      pageSize: 50,
      // Latest activity first, like every inbox (whatsapp_inbox#92): sorting by `id` put a random
      // uuid in charge of who the operator sees first.
      sort: "last_message_at",
      dir: "desc"
    });
    await this.ctrl.load();
    try {
      const off1 = erplora().on("whatsapp_inbox.conversation.assigned", () => this.onDomainEvent());
      const off2 = erplora().on("whatsapp_inbox.message.received", () => this.onDomainEvent());
      this.unsub = () => {
        off1();
        off2();
      };
    } catch {
    }
  }
  disconnectedCallback() {
    window.removeEventListener("erplora:locale-changed", this.onLocaleChange);
    super.disconnectedCallback();
    this.unsub?.();
    this.releaseMedia();
  }
  /** A new message must land in the thread the operator is READING, not only in the list. */
  onDomainEvent() {
    void this.ctrl.load();
    if (this.detail) void this.loadDetail(this.detail.id);
  }
  // ── The thread ────────────────────────────────────────────────────────────
  async loadDetail(conversationId) {
    this.detailError = "";
    try {
      const rows = await erplora().query("whatsapp_inbox.conversations.get", {
        conversation_id: conversationId
      });
      const conversation = Array.isArray(rows) ? rows[0] : rows;
      if (!conversation) {
        this.closeDetail();
        return;
      }
      this.detail = conversation;
      this.assignTo = conversation.assigned_to_id ?? "";
      const page = await erplora().queryPage("whatsapp_inbox.messages.list", {
        limit: THREAD_PAGE,
        sort: "created_at",
        dir: "asc",
        params: { conversation_id: conversationId }
      });
      this.messages = page?.rows ?? [];
      for (const m4 of this.messages) {
        const media = messageMedia(m4);
        if (media && SHOWN_INLINE.has(media.kind)) void this.loadMedia(media.mediaId);
      }
    } catch (e5) {
      this.detailError = e5 instanceof Error ? e5.message : erplora().t(CATALOG, "ui.errLoadThread");
    }
  }
  closeDetail() {
    this.viewing = null;
    this.releaseMedia();
    this.detail = null;
    this.messages = [];
    this.detailError = "";
    this.assignTo = "";
  }
  // ── Attachments (whatsapp_inbox#192) ───────────────────────────────────────
  /** Downloads one attachment once; `retry` starts again after a failure. A reload of the thread
   *  (a new message arriving) keeps what was already downloaded. */
  async loadMedia(mediaId, retry = false) {
    const door2 = mediaDoor();
    const current = this.media[mediaId];
    if (!door2 || current && !(retry && current.status === "error")) return;
    this.media = { ...this.media, [mediaId]: { status: "loading" } };
    let next;
    try {
      next = { status: "ready", url: URL.createObjectURL(await door2.get(mediaId)) };
    } catch {
      next = { status: "error" };
    }
    if (this.media[mediaId]?.status !== "loading") {
      if (next.status === "ready") URL.revokeObjectURL(next.url);
      return;
    }
    this.media = { ...this.media, [mediaId]: next };
  }
  releaseMedia() {
    for (const state of Object.values(this.media)) {
      if (state.status === "ready") URL.revokeObjectURL(state.url);
    }
    this.media = {};
    this.unplayable = /* @__PURE__ */ new Set();
  }
  /** The device cannot play it: said up front by `canPlayType`, or found out when the player
   *  failed on the downloaded file. Either way the owner gets the file instead of silence. */
  playable(media) {
    return !this.unplayable.has(media.mediaId) && devicePlays(media);
  }
  markUnplayable(mediaId) {
    this.unplayable = new Set(this.unplayable).add(mediaId);
  }
  /** Assigns the open conversation, or unassigns it: `employee_id: ''` is the SQL's own contract. */
  async assign() {
    if (!this.detail) return;
    this.detailBusy = true;
    this.detailError = "";
    try {
      await erplora().command("whatsapp_inbox.conversations.assign", {
        conversation_id: this.detail.id,
        employee_id: this.assignTo.trim()
      });
      await this.ctrl.load();
      await this.loadDetail(this.detail.id);
    } catch (e5) {
      this.detailError = domainErrorText2(e5, "ui.errAssign");
    } finally {
      this.detailBusy = false;
    }
  }
  onRowAction(ev) {
    if (ev.detail.actionId === "open") void this.loadDetail(String(ev.detail.row.id));
  }
  // ── Render ────────────────────────────────────────────────────────────────
  renderMedia(media, body) {
    const t5 = (k2) => erplora().t(CATALOG, k2);
    const label = t5(`ui.mediaKind.${media.kind}`);
    const state = this.media[media.mediaId];
    let content;
    if (!mediaDoor()) {
      content = b2`<p class="note" data-testid="whatsapp-inbox-media-unavailable">${t5("ui.mediaUnavailable")}</p>`;
    } else if (!state) {
      content = SHOWN_INLINE.has(media.kind) ? b2`<p class="note">${t5("ui.mediaLoading")}</p>` : b2`<ion-button data-testid="whatsapp-inbox-media-load" size="small" fill="outline"
            @click=${() => this.loadMedia(media.mediaId)}>
            ${t5(media.kind === "document" || !this.playable(media) ? "ui.mediaDownload" : "ui.mediaPlay")}
          </ion-button>`;
    } else if (state.status === "loading") {
      content = b2`<p class="note">${t5("ui.mediaLoading")}</p>`;
    } else if (state.status === "error") {
      content = b2`<p class="err">${t5("ui.mediaError")}</p>
        <ion-button data-testid="whatsapp-inbox-media-retry" size="small" fill="clear"
          @click=${() => this.loadMedia(media.mediaId, true)}>${t5("ui.mediaRetry")}</ion-button>`;
    } else if (media.kind === "image" || media.kind === "sticker") {
      const img = b2`<img src=${state.url} alt=${media.caption || label} />`;
      content = media.kind === "image" ? b2`<button type="button" class="open-photo" data-testid="whatsapp-inbox-media-open"
            aria-label=${t5("ui.viewerOpen")} @click=${() => {
        this.viewing = media.mediaId;
      }}>${img}</button>` : img;
    } else if ((media.kind === "audio" || media.kind === "video") && !this.playable(media)) {
      const name = mediaFileName(media, label);
      content = b2`<p class="note" data-testid="whatsapp-inbox-media-cannot-play">${t5("ui.mediaCannotPlay")}</p>
        <a href=${state.url} download=${name} target="_blank" rel="noopener">${t5("ui.mediaDownload")} ${name}</a>`;
    } else if (media.kind === "audio") {
      content = b2`<audio controls src=${state.url} @error=${() => this.markUnplayable(media.mediaId)}></audio>`;
    } else if (media.kind === "video") {
      content = b2`<video controls playsinline src=${state.url}
        @error=${() => this.markUnplayable(media.mediaId)}></video>`;
    } else {
      const name = mediaFileName(media, label);
      content = b2`<a href=${state.url} download=${name} target="_blank" rel="noopener">
        ${t5("ui.mediaOpen")} ${name}</a>`;
    }
    return b2`<div class="media">
      <span class="kind">${label}${media.filename ? b2` · ${media.filename}` : A}</span>
      ${content}
      ${media.caption && media.caption !== body ? b2`<p class="body">${media.caption}</p>` : A}
    </div>`;
  }
  /** Every downloaded photo of the thread, oldest first, so the viewer pages through them all. */
  renderViewer() {
    if (!this.viewing) return A;
    const photos = [];
    for (const m4 of this.messages) {
      const media = messageMedia(m4);
      const state = media && media.kind === "image" ? this.media[media.mediaId] : void 0;
      if (!media || state?.status !== "ready") continue;
      const alt = media.caption || erplora().t(CATALOG, "ui.mediaKind.image");
      photos.push({ mediaId: media.mediaId, item: { src: state.url, alt, type: "img" } });
    }
    const index = photos.findIndex((p4) => p4.mediaId === this.viewing);
    if (index < 0) return A;
    const labels = Object.fromEntries(
      Object.entries(VIEWER_LABELS).map(([k2, key]) => [k2, erplora().t(CATALOG, key)])
    );
    return b2`<ok-lightbox open .items=${photos.map((p4) => p4.item)} .index=${index}
      .labels=${labels} @ok-close=${() => {
      this.viewing = null;
    }}></ok-lightbox>`;
  }
  renderMessage(m4) {
    const t5 = (k2) => erplora().t(CATALOG, k2);
    const side = m4.direction === "outbound" || m4.direction === "inbound" ? m4.direction : "unknown";
    const media = messageMedia(m4);
    const bodyless = !media && !m4.body && m4.message_type && m4.message_type !== "text";
    return b2`<div class=${`msg ${side}`}>
      ${side === "unknown" ? b2`<span class="kind">${t5("ui.unknownDirection")} · ${m4.direction}</span>` : A}
      ${media ? this.renderMedia(media, m4.body) : A}
      ${bodyless ? b2`<span class="kind">${m4.message_type}</span>` : A}
      ${m4.body ? b2`<p class="body">${m4.body}</p>` : A}
      ${m4.media_url ? b2`<span class="kind">${t5("ui.attachment")}</span>` : A}
      <span class="when">${whenText(m4.created_at, true)}</span>
    </div>`;
  }
  renderDetail() {
    const c5 = this.detail;
    if (!c5) return A;
    const t5 = (k2) => erplora().t(CATALOG, k2);
    return b2`<section class="detail">
      <div class="detail-head">
        <h3>${c5.contact_name || c5.contact_phone}</h3>
        <span class="phone">${c5.contact_phone}</span>
        <ok-status-pill tone=${c5.status === "closed" ? "neutral" : "success"} size="sm">
          ${c5.status === "closed" ? t5("ui.statusClosed") : t5("ui.statusActive")}
        </ok-status-pill>
        <span class="spacer"></span>
        <ion-button data-testid="whatsapp-inbox-detail-close" size="small" fill="clear" @click=${() => this.closeDetail()}>${t5("ui.closeView")}</ion-button>
      </div>
      ${this.detailError ? b2`<p class="err" data-testid="whatsapp-inbox-detail-error">${this.detailError}</p>` : A}
      <div class="thread">
        ${this.messages.length ? this.messages.map((m4) => this.renderMessage(m4)) : b2`<p class="empty">${t5("ui.emptyThread")}</p>`}
      </div>
      ${this.renderViewer()}
      ${can("whatsapp_inbox.manage_settings") ? b2`<div class="assign">
            <ion-input data-testid="whatsapp-inbox-assign-to" mode="md" fill="outline" label-placement="floating" label=${t5("ui.assignedTo")}
              placeholder=${t5("ui.assignPlaceholder")} .value=${this.assignTo}
              @ionInput=${(e5) => this.assignTo = e5.target.value ?? ""}></ion-input>
            <ion-button data-testid="whatsapp-inbox-assign-submit" size="small" ?disabled=${this.detailBusy} @click=${() => this.assign()}>
              ${this.assignTo.trim() ? t5("ui.assign") : t5("ui.unassign")}
            </ion-button>
          </div>` : A}
      <p class="note">${t5("ui.threadRepliesElsewhere")}</p>
    </section>`;
  }
  render() {
    const t5 = (k2) => erplora().t(CATALOG, k2);
    return b2`<div class="page">
        <header>
          <h2>${t5("ui.inboxTitle")}</h2>
        </header>
        ${this.ctrl?.error ? b2`<p class="err" data-testid="whatsapp-inbox-load-error">${this.ctrl.error}</p>` : A}
        ${this.renderDetail()}
        <ok-data-table testid="whatsapp-inbox-table" .serverSide=${true} .views=${true} .fill=${true} .actions=${this.rowActions} .rowClickable=${true} .cardTitle=${(row) => String(row.contact_name ?? row.contact_phone ?? "\u2014")} .columns=${this.columns} .rows=${this.ctrl?.rows ?? []} .total=${this.ctrl?.total ?? 0} .page=${this.ctrl?.state.page ?? 0} .pageSize=${this.ctrl?.state.pageSize ?? 50} .sort=${this.ctrl?.state.sort} .sortDir=${this.ctrl?.state.dir ?? "asc"} .searchable=${true} .searchPlaceholder=${t5("ui.searchInbox")} .emptyMessage=${this.ctrl?.loading ? t5("ui.loading") : t5("ui.emptyInbox")} @rowAction=${(e5) => this.onRowAction(e5)} @rowClick=${(e5) => this.onRowAction({ detail: { actionId: "open", row: e5.detail.row } })} @pageChange=${(e5) => this.ctrl.setPage(e5.detail)} @pageSizeChange=${(e5) => this.ctrl.setPageSize(e5.detail)} @sortChange=${(e5) => this.ctrl.setSort(e5.detail.sort, e5.detail.dir)} @searchChange=${(e5) => this.ctrl.setSearch(e5.detail)} @filterChange=${(e5) => this.ctrl.setFilter(e5.detail.col, e5.detail.value)}></ok-data-table>
      </div>`;
  }
};
__decorateClass([
  r5()
], ErpWhatsappInboxInbox.prototype, "tick", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxInbox.prototype, "detail", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxInbox.prototype, "messages", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxInbox.prototype, "detailError", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxInbox.prototype, "detailBusy", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxInbox.prototype, "media", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxInbox.prototype, "unplayable", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxInbox.prototype, "viewing", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxInbox.prototype, "assignTo", 2);
define("erp-whatsapp-inbox-inbox", ErpWhatsappInboxInbox);

// @erplora/outfitkit/dist/ok-inline-feedback.js
var __defProp5 = Object.defineProperty;
var __decorateClass5 = (decorators, target, key, kind) => {
  var result = void 0;
  for (var i7 = decorators.length - 1, decorator; i7 >= 0; i7--)
    if (decorator = decorators[i7])
      result = decorator(target, key, result) || result;
  if (result) __defProp5(target, key, result);
  return result;
};
var DEFAULT_LABELS3 = {
  dismiss: "Dismiss"
};
var OkInlineFeedback = class extends i3 {
  constructor() {
    super(...arguments);
    this.tone = "info";
    this.dismissible = false;
    this.hidden = false;
    this.labels = {};
    this.hasActions = false;
    this.onActionsSlotChange = (e5) => {
      const slot = e5.target;
      this.hasActions = slot.assignedNodes({ flatten: true }).length > 0;
    };
  }
  static {
    this.styles = i`
    :host {
      /* Vars overridable (estilo Ionic), default = cadena --ok-* → --ion-* → hex.
         --tone-color y --tone-icon se reasignan por tone abajo. */
      --tone-color: var(--ok-primary, var(--ion-color-primary, #3880ff));
      --background-opacity: 0.1;
      --color: var(--ok-text, var(--ion-text-color, #1c1b17));
      --border-radius: var(--ok-radius, var(--ion-border-radius, 8px));
      --padding: var(--ok-spacing, var(--ion-padding, 16px));
      --accent-width: 4px;
      --font: var(--ok-font, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif);

      /* Responsive: el banner ocupa el ancho del contenedor. */
      display: block;
      width: 100%;
      font-family: var(--font);
      box-sizing: border-box;
    }
    :host([hidden]) { display: none; }

    /* Mapa de tonos → color Ionic + icono por defecto. */
    :host([tone='success']) { --tone-color: var(--ok-success, var(--ion-color-success, #2dd55b)); }
    :host([tone='warning']) { --tone-color: var(--ok-warning, var(--ion-color-warning, #ffc409)); }
    :host([tone='danger'])  { --tone-color: var(--ok-danger, var(--ion-color-danger, #c5000f)); }
    :host([tone='neutral']) { --tone-color: var(--ok-medium, var(--ion-color-medium, #5f5f5f)); }
    /* info / sin tono → primary (default ya aplicado en :host). */

    .box {
      position: relative;
      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
      padding: var(--padding);
      border-radius: var(--border-radius);
      border-inline-start: var(--accent-width) solid var(--tone-color);
      /* Fondo tonal: el color del tono con baja opacidad (color-mix con fallback al borde fino). */
      background: color-mix(in srgb, var(--tone-color) calc(var(--background-opacity) * 100%), transparent);
      color: var(--color);
    }

    .icon {
      flex: 0 0 auto;
      font-size: 1.4rem;
      line-height: 1;
      color: var(--tone-color);
      margin-top: 0.05rem;
    }

    .content {
      flex: 1 1 auto;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    .row {
      display: flex;
      align-items: flex-start;
      gap: 1rem;
    }
    .text {
      flex: 1 1 auto;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
    }
    .heading {
      font-weight: 700;
      font-size: 0.98rem;
      line-height: 1.3;
    }
    .body {
      font-size: 0.92rem;
      line-height: 1.45;
    }
    .actions {
      flex: 0 0 auto;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    /* Si no hay actions, el slot queda vacío y no ocupa espacio. */
    .actions.empty { display: none; }

    .close {
      flex: 0 0 auto;
      background: none;
      border: 0;
      cursor: pointer;
      padding: 0.15rem;
      margin: -0.15rem -0.15rem 0 0;
      color: inherit;
      opacity: 0.6;
      font-size: 1.2rem;
      line-height: 1;
      border-radius: 4px;
      transition: background-color var(--ok-transition, 150ms ease), color var(--ok-transition, 150ms ease),
        border-color var(--ok-transition, 150ms ease), box-shadow var(--ok-transition, 150ms ease),
        opacity 0.15s ease, transform 120ms ease;
    }
    @media (hover: hover) {
      .close:hover { opacity: 1; background: rgba(var(--ion-text-color-rgb, 24, 24, 27), 0.07); }
    }
    .close:active { transform: scale(var(--ok-press-scale, 0.97)); }

    /* Móvil: las actions bajan bajo el texto (apiladas a ancho completo). */
    @media (max-width: 640px) {
      .row { flex-direction: column; align-items: stretch; }
      .actions { width: 100%; }
    }
    @media (prefers-reduced-motion: reduce) {
      .close:hover,
      .close:active { transform: none; }
    }
  `;
  }
  // Textos efectivos: defaults en inglés + overrides del consumidor.
  get t() {
    return { ...DEFAULT_LABELS3, ...this.labels };
  }
  // Icono por defecto según el tono (overridable por la prop `icon`).
  defaultIcon() {
    switch (this.tone) {
      case "success":
        return iconCheckmarkCircle;
      case "warning":
        return iconWarning;
      case "danger":
        return iconAlertCircle;
      case "neutral":
        return iconInformationCircle;
      case "info":
      default:
        return iconInformationCircle;
    }
  }
  // Oculta el banner y avisa al consumidor; éste puede revertir restaurando `hidden=false`.
  dismiss() {
    this.hidden = true;
    this.dispatchEvent(new CustomEvent("ok-dismiss", { bubbles: true, composed: true }));
  }
  render() {
    const iconName = this.icon ?? this.defaultIcon();
    return b2`
      <div class="box" role="status">
        <ion-icon class="icon" .icon=${okIcon(iconName)} aria-hidden="true"></ion-icon>
        <div class="content">
          <div class="row">
            <div class="text">
              ${this.heading ? b2`<div class="heading">${this.heading}</div>` : null}
              <div class="body"><slot></slot></div>
            </div>
            <div class="actions ${this.hasActions ? "" : "empty"}">
              <slot name="actions" @slotchange=${this.onActionsSlotChange}></slot>
            </div>
          </div>
        </div>
        ${this.dismissible ? b2`
              <button class="close" aria-label=${this.t.dismiss} @click=${this.dismiss}>
                <ion-icon .icon=${iconClose} aria-hidden="true"></ion-icon>
              </button>
            ` : null}
      </div>
    `;
  }
};
__decorateClass5([
  n4({ type: String, reflect: true })
], OkInlineFeedback.prototype, "tone");
__decorateClass5([
  n4({ type: String })
], OkInlineFeedback.prototype, "heading");
__decorateClass5([
  n4({ type: String })
], OkInlineFeedback.prototype, "icon");
__decorateClass5([
  n4({ type: Boolean, reflect: true })
], OkInlineFeedback.prototype, "dismissible");
__decorateClass5([
  n4({ type: Boolean, reflect: true })
], OkInlineFeedback.prototype, "hidden");
__decorateClass5([
  n4({ attribute: false })
], OkInlineFeedback.prototype, "labels");
__decorateClass5([
  r5()
], OkInlineFeedback.prototype, "hasActions");
define("ok-inline-feedback", OkInlineFeedback);

// ui/lib/whatsapp-uses.ts
var MODULE_ID = "whatsapp_inbox";
var WHATSAPP_USES = [
  {
    family: "appointment-from-whatsapp",
    // The notice the salon's «Confirmar» owes the customer (whatsapp_inbox#125). Its floor is
    // `appointments` 1.1.26, well under the 1.1.73 this card already demands, so no hub can accept
    // the booking recipe and refuse this one.
    companions: ["appointment-confirmed-to-whatsapp"],
    module: "appointments",
    witness: "appointments.settings.get",
    probe: (client) => client.queryOptional("appointments.settings.get"),
    policy: {
      read: "appointments.settings.get",
      write: "appointments.settings.set_auto_confirm_online",
      field: "auto_confirm_online",
      ask: (client) => client.queryOptional("appointments.settings.get"),
      set: (client, on) => client.commandOptional("appointments.settings.set_auto_confirm_online", { auto_confirm_online: on }),
      autoKey: "ui.useAppointmentsPolicyAuto",
      reviewKey: "ui.policyReview",
      reviewHelpKey: "ui.useAppointmentsPolicyReviewHelp",
      errorKey: "ui.useAppointmentsPolicyError",
      // Appointments creates the row with the column ON, and it is what the market does: Square,
      // Cal.com and SimplyBook all default to booking without review.
      defaultOn: true
    },
    icon: "calendar-outline",
    nameKey: "ui.useAppointmentsName",
    summaryKey: "ui.useAppointmentsSummary",
    consentKey: "ui.useAppointmentsConsent",
    doneKey: "ui.useAppointmentsDone"
  },
  {
    // whatsapp_inbox#126: a restaurant with Reservations connected its number and was offered
    // «Reservar citas», which is not what it does — while `reservation-from-whatsapp` had been
    // shipped in `flows/` all along. Same card, same one tap, same one decision; the only thing
    // that changes is whose diary it is.
    family: "reservation-from-whatsapp",
    // Reservations ships no notice-on-confirm recipe — the half of the sentence #125 had to carry
    // for the salon does not exist here — so this card promises exactly one thing and carries it.
    companions: [],
    module: "reservations",
    witness: "reservations.settings.get",
    probe: (client) => client.queryOptional("reservations.settings.get"),
    policy: {
      read: "reservations.settings.get",
      write: "reservations.settings.set_auto_confirm",
      field: "auto_confirm",
      ask: (client) => client.queryOptional("reservations.settings.get"),
      set: (client, on) => client.commandOptional("reservations.settings.set_auto_confirm", { auto_confirm: on }),
      autoKey: "ui.useReservationsPolicyAuto",
      reviewKey: "ui.policyReview",
      reviewHelpKey: "ui.useReservationsPolicyReviewHelp",
      errorKey: "ui.useReservationsPolicyError",
      // 🔴 The OPPOSITE of Appointments, and it is measured, not mirrored: Reservations creates the
      // column `auto_confirm INTEGER NOT NULL DEFAULT 0` (`migrations/postgres/001_init.sql`), so a
      // restaurant that never opened its settings is REVIEWING every table. Copying `true` from the
      // card above would paint «se confirman solas» over a hub that holds every booking for the
      // owner — and the guard at the end of `whatsapp-uses.test.ts` reads that DEFAULT off
      // `origin/main` in both directions, so neither side can drift alone.
      defaultOn: false
    },
    icon: "restaurant-outline",
    nameKey: "ui.useReservationsName",
    summaryKey: "ui.useReservationsSummary",
    consentKey: "ui.useReservationsConsent",
    doneKey: "ui.useReservationsDone"
  }
];
var readBookingPolicy = (client, use) => use.policy.ask(client);
var writeBookingPolicy = (client, use, on) => use.policy.set(client, on);
function bookingPolicyOn(answer, use) {
  const row = Array.isArray(answer) ? answer[0] : answer;
  if (row === null || typeof row !== "object") return use.policy.defaultOn;
  const value = row[use.policy.field];
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string" && value.trim() !== "") return !["0", "f", "false", "no"].includes(value.trim().toLowerCase());
  return use.policy.defaultOn;
}
function templateState(installed) {
  if (installed === void 0) return "unknown";
  if (installed === null) return "off";
  if (typeof installed !== "object") return "unknown";
  const { enabled } = installed;
  if (typeof enabled !== "boolean") return "unknown";
  return enabled ? "on" : "paused";
}
var AUTOMATIONS_MODULE = "flows";
var probeAutomations = (client) => client.queryOptional("flows.drafts.list");
var NEIGHBOUR_NAME_KEYS = {
  appointments: "ui.neighbourAppointments",
  customers: "ui.neighbourCustomers",
  reservations: "ui.neighbourReservations",
  services: "ui.neighbourServices",
  staff: "ui.neighbourStaff"
};
var APPS_PATH = "/apps";
var AUTOMATIONS_PATH = `/m/${AUTOMATIONS_MODULE}/automations`;

// ui/components/erp-whatsapp-inbox-settings/erp-whatsapp-inbox-settings.ts
var CATALOG2 = { es: es_default, en: en_default };
var DISCARD_SENTENCE = {
  template_floor_module_missing: "ui.usesNeedMissingModule",
  template_floor_module_paused: "ui.usesNeedPausedModule",
  template_floor_module_too_old: "ui.usesNeedUpdatedModule"
};
function erplora2() {
  const c5 = globalThis.erplora;
  if (!c5) throw new Error("erplora SDK no inicializado por el shell");
  return c5;
}
function door() {
  const client = erplora2();
  if (typeof client.forModule !== "function") return null;
  const flows = client.forModule(MODULE_ID).flows;
  if (typeof flows?.activateTemplate !== "function") return null;
  return flows;
}
function discardReason(use, discards, t5) {
  for (const d3 of discards) {
    if (d3.family !== use.family || !d3.requires) continue;
    const sentence = DISCARD_SENTENCE[d3.code];
    const nameKey = NEIGHBOUR_NAME_KEYS[d3.requires.module];
    if (!sentence || !nameKey) continue;
    return t5(sentence, {
      use: t5(use.nameKey),
      module: t5(nameKey),
      floor: d3.requires.floor,
      installed: d3.requires.installed ?? ""
    });
  }
  return null;
}
var ErpWhatsappInboxSettings = class extends i3 {
  constructor() {
    super(...arguments);
    this.built = {};
    this.templatesFailed = false;
    this.discards = [];
    this.missing = /* @__PURE__ */ new Set();
    this.loaded = false;
    this.asking = "";
    this.busy = "";
    this.cardError = {};
    this.justActivated = "";
    this.policy = {};
    this.policyFailed = {};
    this.hasAutomations = false;
    this.hubTooOld = false;
    this.connectAvailable = false;
  }
  static {
    this.styles = i`
    :host { display: block; padding: 12px; }
    h2 { margin: 0 0 4px; font-size: 1.25rem; }
    h3 { margin: 20px 0 6px; font-size: 1rem; }
    p.help { margin: 4px 0 8px; color: var(--ion-color-medium, #6b7280); font-size: 0.9rem; }
    .card {
      border: 1px solid var(--ion-color-step-150, #e5e7eb);
      border-radius: 12px; padding: 12px; margin: 8px 0;
    }
    .card header { display: flex; align-items: center; gap: 8px; }
    .card header h4 { margin: 0; font-size: 1rem; flex: 1; }
    .state { font-weight: 600; font-size: 0.85rem; }
    .state.is-on { color: var(--ion-color-success, #16a34a); }
    .consent { margin-top: 10px; padding: 10px; border-radius: 10px;
      background: var(--ion-color-step-50, #f8fafc); }
    .consent p { margin: 0 0 8px; }
    .done { margin: 8px 0 0; }
    ion-segment { margin-top: 10px; }
    details { margin-top: 24px; }
    summary { cursor: pointer; padding: 8px 0; }
    .advanced { margin-top: 16px; }
    /* Three viewports, and the same rule at all three: nothing here caps its width. The
       ion-content around this screen already sets the only horizontal limit -- its responsive
       gutter -- and a card that stops at 640px reads on a desk as a narrow island in a fluid page
       (Ioan, 2026-09-06). Pinned by «the screen stays fluid at every width» in the test. */
  `;
  }
  connectedCallback() {
    super.connectedCallback();
    this.connectAvailable = Boolean(customElements.get("erp-whatsapp-connect"));
    void this.load();
  }
  /** One round: what is built, which neighbours are here, and the policy of whatever is running. */
  async load() {
    const client = erplora2();
    const flows = door();
    this.hubTooOld = flows === null;
    if (flows) {
      try {
        const listed = await flows.templates();
        const built = {};
        for (const t5 of listed) built[t5.family] = t5.installed ?? null;
        this.built = built;
        this.templatesFailed = false;
      } catch {
        this.templatesFailed = true;
        this.built = {};
      }
      if (typeof flows.templateDiscards === "function") {
        try {
          this.discards = await flows.templateDiscards();
        } catch (e5) {
          console.warn(`[${MODULE_ID}] could not read why the hub left recipes out`, e5);
          this.discards = [];
        }
      }
    }
    const missing = /* @__PURE__ */ new Set();
    await Promise.all(
      WHATSAPP_USES.map(async (use) => {
        try {
          const answer = await use.probe(client);
          if (answer === void 0) missing.add(use.module);
        } catch {
        }
      })
    );
    this.missing = missing;
    try {
      this.hasAutomations = await probeAutomations(client) !== void 0;
    } catch {
      this.hasAutomations = false;
    }
    await Promise.all(WHATSAPP_USES.map((use) => this.loadPolicy(use)));
    this.loaded = true;
  }
  /** The diary's own answer, or the diary's own default when the salon never configured it. */
  async loadPolicy(use) {
    if (this.missing.has(use.module)) return;
    try {
      const answer = await readBookingPolicy(erplora2(), use);
      this.policy = { ...this.policy, [use.family]: bookingPolicyOn(answer, use) };
    } catch {
      this.policy = { ...this.policy, [use.family]: use.policy.defaultOn };
    }
  }
  t(key, params) {
    return erplora2().t(CATALOG2, key, params);
  }
  go(path) {
    window.history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }
  /**
   * Turns on everything the card promised — its own recipe and the companions that finish the
   * sentence the owner consented to (whatsapp_inbox#125) — and re-reads the listing.
   *
   * The listing is authoritative on purpose: the door answers with the flow it built, but what the
   * card paints is what the hub says is there. Trusting the write would make a card that reads
   * «Activo» over a flow that a later refusal never created.
   *
   * **The card's own recipe goes first, and a half-done activation is undone.** One switch cannot
   * paint two answers: left half on, the card would read «Activo» while the customer keeps waiting
   * for the confirmation that never leaves — the very silence of #125, now with a screen saying it
   * works, and no way offered to retry the half that failed. Undoing puts the card back where the
   * owner can press «Activar» again, and the refresh below still paints whatever really survived.
   */
  async activate(use) {
    const flows = door();
    if (!flows?.activateTemplate) return;
    this.busy = use.family;
    this.cardError = { ...this.cardError, [use.family]: null };
    const turnedOn = [];
    try {
      for (const family of [use.family, ...use.companions]) {
        await flows.activateTemplate(family);
        turnedOn.push(family);
      }
      this.asking = "";
      await this.refresh(flows);
      this.justActivated = use.family;
      await this.loadPolicy(use);
    } catch (e5) {
      this.asking = "";
      this.cardError = { ...this.cardError, [use.family]: activationError(e5) };
      await this.undo(flows, turnedOn);
      await this.refresh(flows);
    } finally {
      this.busy = "";
    }
  }
  /**
   * Stops what a failed activation had already started, the card's own recipe LAST for the same
   * reason {@link deactivate} does it in that order.
   *
   * A rollback that fails is not swallowed: the card keeps the error that started this, the console
   * carries the second one, and the refresh that follows paints what is really still running —
   * «Activo» over the half that survived, never a silent «off» with an automation behind it.
   */
  async undo(flows, turnedOn) {
    for (const family of [...turnedOn].reverse()) {
      try {
        await flows.deactivateTemplate?.(family);
      } catch (e5) {
        console.warn(`[${MODULE_ID}] could not undo a half-done activation of ${family}`, e5);
      }
    }
  }
  /**
   * Stops everything the card promised — the companions FIRST, its own recipe LAST.
   *
   * The order is the guarantee, not a detail: turning the card's recipe off first would leave the
   * hub texting customers behind a card that already reads «Desactivada», an automation running
   * where the owner was told there is none. Failing halfway lands on the same rule — the refresh
   * repaints from the hub, so what is still running still reads as running.
   */
  async deactivate(use) {
    const flows = door();
    if (!flows?.deactivateTemplate) return;
    this.busy = use.family;
    this.cardError = { ...this.cardError, [use.family]: null };
    try {
      for (const family of [...use.companions].reverse()) await flows.deactivateTemplate(family);
      await flows.deactivateTemplate(use.family);
      this.justActivated = "";
      await this.refresh(flows);
    } catch (e5) {
      this.cardError = { ...this.cardError, [use.family]: activationError(e5) };
      await this.refresh(flows);
    } finally {
      this.busy = "";
    }
  }
  async refresh(flows) {
    try {
      const listed = await flows.templates();
      const built = {};
      for (const t5 of listed) built[t5.family] = t5.installed ?? null;
      this.built = built;
    } catch {
      this.templatesFailed = true;
    }
  }
  /** The one decision, written where it lives: in the diary, through its narrow command. */
  async setPolicy(use, on) {
    this.policyFailed = { ...this.policyFailed, [use.family]: false };
    try {
      await writeBookingPolicy(erplora2(), use, on);
      this.policy = { ...this.policy, [use.family]: on };
    } catch {
      this.policyFailed = { ...this.policyFailed, [use.family]: true };
    }
  }
  // ── Render ─────────────────────────────────────────────────────────────────────────────────────
  render() {
    return b2`
      <h2>${this.t("ui.settingsTitle")}</h2>
      ${this.renderConnect()}
      ${this.renderUses()}
      ${this.renderAdvanced()}
    `;
  }
  /** Step 1 — the number. The popup is Meta's and the element that runs it is the shell's. */
  renderConnect() {
    return b2`
      <h3>${this.t("ui.stepNumber")}</h3>
      ${this.connectAvailable ? b2`<erp-whatsapp-connect></erp-whatsapp-connect>` : b2`<ok-inline-feedback data-testid="whatsapp-settings-connect-needs-newer-hub" tone="warning">${this.t("ui.helpConnectNeedsNewerHub")}</ok-inline-feedback>`}
      <p class="help">${this.t("ui.helpConnectScanQr")}</p>
    `;
  }
  /** Step 2 — what the number is for. One card per use this hub can actually offer. */
  renderUses() {
    const heading = b2`<h3>${this.t("ui.stepUses")}</h3>`;
    if (!this.loaded) {
      return b2`${heading}<ion-spinner name="crescent" data-testid="whatsapp-settings-uses-loading"></ion-spinner>`;
    }
    if (this.hubTooOld) {
      return b2`${heading}
        <ok-inline-feedback data-testid="whatsapp-settings-uses-needs-newer-hub" tone="warning">${this.t("ui.usesNeedsNewerHub")}</ok-inline-feedback>`;
    }
    if (this.templatesFailed) {
      return b2`${heading}
        <ok-inline-feedback data-testid="whatsapp-settings-uses-error" tone="danger">${this.t("ui.errTemplates")}</ok-inline-feedback>`;
    }
    const installed = WHATSAPP_USES.filter((use) => !this.missing.has(use.module));
    const available = installed.filter((use) => this.built[use.family] !== void 0);
    const blocked = installed.filter((use) => this.built[use.family] === void 0).map((use) => ({ use, reason: discardReason(use, this.discards, (k2, p4) => this.t(k2, p4)) })).filter((b3) => b3.reason !== null);
    const reasons = blocked.map(
      ({ use, reason }) => b2`<ok-inline-feedback data-testid=${`whatsapp-settings-uses-blocked-${use.family}`} tone="warning">${reason}</ok-inline-feedback>`
    );
    const goToApps = b2`<ion-button data-testid="whatsapp-settings-uses-go-to-apps" size="small" @click=${() => this.go(APPS_PATH)}>
      ${this.t("ui.usesGoToApps")}
    </ion-button>`;
    if (available.length === 0) {
      if (blocked.length > 0) return b2`${heading}${reasons}${goToApps}`;
      const why = installed.length === 0 ? "ui.usesNeedBookingModule" : "ui.usesNeedNewerBookingModule";
      return b2`${heading}
        <ok-inline-feedback data-testid="whatsapp-settings-uses-need-module" tone="warning">${this.t(why)}</ok-inline-feedback>
        ${goToApps}`;
    }
    return b2`${heading}${available.map((use) => this.renderUse(use))}${blocked.length > 0 ? b2`${reasons}${goToApps}` : A}`;
  }
  renderUse(use) {
    const stateOf = templateState(this.built[use.family]);
    const on = stateOf === "on";
    const error = this.cardError[use.family] ?? null;
    return b2`
      <section class="card">
        <header>
          <ion-icon name=${use.icon} aria-hidden="true"></ion-icon>
          <h4>${this.t(use.nameKey)}</h4>
          ${stateOf === "on" || stateOf === "paused" ? b2`<span class="state ${on ? "is-on" : ""}" data-testid=${`whatsapp-settings-state-${use.family}`}
                >${this.t(on ? "ui.stateOn" : "ui.stateOff")}</span
              >` : A}
        </header>
        <p class="help">${this.t(use.summaryKey)}</p>

        ${on ? b2`<ion-button
              size="small"
              fill="clear"
              data-testid=${`whatsapp-settings-deactivate-${use.family}`}
              ?disabled=${this.busy === use.family}
              @click=${() => this.deactivate(use)}
            >${this.t("ui.turnOff")}</ion-button>` : b2`<ion-button
              size="small"
              data-testid=${`whatsapp-settings-activate-${use.family}`}
              ?disabled=${this.busy === use.family}
              @click=${() => {
      this.asking = use.family;
      this.cardError = { ...this.cardError, [use.family]: null };
    }}
            >${this.t("ui.activate")}</ion-button>`}

        ${this.asking === use.family ? this.renderConsent(use) : A}
        ${error ? b2`<ok-inline-feedback data-testid=${`whatsapp-settings-card-error-${use.family}`} tone="danger">${errorText(error, (k2) => this.t(k2))}</ok-inline-feedback>` : A}
        ${on && this.justActivated === use.family ? b2`<p class="done" data-testid=${`whatsapp-settings-activated-${use.family}`}>${this.t(use.doneKey)}</p>` : A}
        ${on ? this.renderPolicy(use) : A}
      </section>
    `;
  }
  /** The consent: ONE sentence naming the consequence, and two buttons. Nothing runs until «yes». */
  renderConsent(use) {
    return b2`
      <div class="consent">
        <p>${this.t(use.consentKey)}</p>
        <ion-button
          size="small"
          data-testid=${`whatsapp-settings-confirm-activate-${use.family}`}
          ?disabled=${this.busy === use.family}
          @click=${() => this.activate(use)}
        >${this.t("ui.activate")}</ion-button>
        <ion-button
          size="small"
          fill="clear"
          data-testid=${`whatsapp-settings-cancel-activate-${use.family}`}
          @click=${() => {
      this.asking = "";
    }}
        >${this.t("ui.notNow")}</ion-button>
      </div>
    `;
  }
  /**
   * Step 3 — the one decision, and it is the diary's. Only once there is something taking bookings.
   *
   * **Every sentence here comes off the use, not off this method** (whatsapp_inbox#126). A salon
   * reviews «citas» in the Agenda and a restaurant reviews «reservas» in Reservas: with the strings
   * pinned in the markup, the second card told a bar its TABLES waited in a diary it does not have,
   * and blamed a failed save on appointments it never takes.
   */
  renderPolicy(use) {
    const auto = this.policy[use.family] ?? use.policy.defaultOn;
    return b2`
      <ion-segment
        data-testid=${`whatsapp-settings-policy-${use.family}`}
        .value=${auto ? "auto" : "review"}
        @ionChange=${(e5) => this.setPolicy(use, e5.detail?.value !== "review")}
      >
        <ion-segment-button data-testid=${`whatsapp-settings-policy-auto-${use.family}`} value="auto"><ion-label>${this.t(use.policy.autoKey)}</ion-label></ion-segment-button>
        <ion-segment-button data-testid=${`whatsapp-settings-policy-review-${use.family}`} value="review"><ion-label>${this.t(use.policy.reviewKey)}</ion-label></ion-segment-button>
      </ion-segment>
      ${auto ? A : b2`<p class="help">${this.t(use.policy.reviewHelpKey)}</p>`}
      ${this.policyFailed[use.family] ? b2`<ok-inline-feedback data-testid=${`whatsapp-settings-policy-error-${use.family}`} tone="danger">${this.t(use.policy.errorKey)}</ok-inline-feedback>` : A}
    `;
  }
  /**
   * Advanced — exactly where it always was, just not on the way (ADR-0470 §4).
   *
   * Steps, the prompt, each of the fourteen permissions with «Limits» and «Revoke», and the History
   * all stay in Automations: nothing was hidden. The link only appears when that module is here,
   * because a door to a module that is not installed is a dead end wearing a label.
   */
  renderAdvanced() {
    return b2`
      ${this.hasAutomations ? b2`<div class="advanced">
            <ion-button
              size="small"
              fill="clear"
              data-testid="whatsapp-settings-advanced-automations"
              @click=${() => this.go(AUTOMATIONS_PATH)}
            >${this.t("ui.advancedInAutomations")}</ion-button>
          </div>` : A}
      <details>
        <summary>${this.t("ui.advancedMetaTemplates")}</summary>
        <erp-whatsapp-inbox-templates></erp-whatsapp-inbox-templates>
      </details>
    `;
  }
};
__decorateClass([
  r5()
], ErpWhatsappInboxSettings.prototype, "built", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxSettings.prototype, "templatesFailed", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxSettings.prototype, "discards", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxSettings.prototype, "missing", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxSettings.prototype, "loaded", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxSettings.prototype, "asking", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxSettings.prototype, "busy", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxSettings.prototype, "cardError", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxSettings.prototype, "justActivated", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxSettings.prototype, "policy", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxSettings.prototype, "policyFailed", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxSettings.prototype, "hasAutomations", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxSettings.prototype, "hubTooOld", 2);
__decorateClass([
  r5()
], ErpWhatsappInboxSettings.prototype, "connectAvailable", 2);
function activationError(e5) {
  const code = e5?.code ?? "";
  if (code === "forbidden" || code === "unauthorized" || code === "flow.template_not_yours") {
    return { key: "ui.activateForbidden" };
  }
  const detail = e5 instanceof Error ? e5.message : "";
  return detail ? { detail } : { key: "ui.errActivate" };
}
var errorText = (error, t5) => "key" in error ? t5(error.key) : error.detail;
define("erp-whatsapp-inbox-settings", ErpWhatsappInboxSettings);

// ui/lib/meta-door-refusal.ts
var SOURCE_LANG2 = "en";
function doorErrorCode(e5) {
  const code = e5?.code;
  return typeof code === "string" ? code : "";
}
function textFor2(catalog, lang, key) {
  const ui = catalog[lang]?.ui;
  const bucket = ui?.doorRefusal;
  const text3 = key ? bucket?.[key] : void 0;
  return typeof text3 === "string" && text3.trim() ? text3 : "";
}
function unknownText(catalog, lang, key, code) {
  const ui = catalog[lang]?.ui;
  const text3 = ui?.[key];
  if (typeof text3 !== "string" || !text3.trim()) return "";
  return text3.replaceAll("{code}", code);
}
function doorRefusalText(catalog, locale, e5) {
  const code = doorErrorCode(e5);
  const declared = textFor2(catalog, locale, code) || textFor2(catalog, SOURCE_LANG2, code);
  if (declared) return declared;
  const key = code ? "doorRefusalUnknown" : "doorRefusalNoCode";
  return unknownText(catalog, locale, key, code) || unknownText(catalog, SOURCE_LANG2, key, code) || code;
}

// ui/lib/meta-template-status.ts
var META_TEMPLATE_STATES = [
  "not_sent",
  "pending",
  "approved",
  "rejected",
  "paused",
  "disabled",
  "deleted"
];
var VIEWS = {
  not_sent: { labelKey: "ui.metaNotSent", actionKey: "ui.metaActionNotSent", tone: "info" },
  pending: { labelKey: "ui.metaPending", actionKey: "ui.metaActionPending", tone: "info" },
  approved: { labelKey: "ui.metaApproved", actionKey: "ui.metaActionApproved", tone: "ok" },
  rejected: { labelKey: "ui.metaRejected", actionKey: "ui.metaActionRejected", tone: "problem" },
  paused: { labelKey: "ui.metaPaused", actionKey: "ui.metaActionPaused", tone: "problem" },
  disabled: { labelKey: "ui.metaDisabled", actionKey: "ui.metaActionDisabled", tone: "problem" },
  deleted: { labelKey: "ui.metaDeleted", actionKey: "ui.metaActionDeleted", tone: "problem" },
  unknown: { labelKey: "", actionKey: "ui.metaActionUnknown", tone: "info" }
};
function metaTemplateState(raw) {
  const value = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  return META_TEMPLATE_STATES.includes(value) ? value : "unknown";
}
function metaTemplateView(raw) {
  const state = metaTemplateState(raw);
  return { state, ...VIEWS[state] };
}

// ui/lib/meta-template-import.ts
var MEDIA_HEADERS = /* @__PURE__ */ new Set(["IMAGE", "VIDEO", "DOCUMENT"]);
var CATEGORIES = /* @__PURE__ */ new Set(["MARKETING", "UTILITY", "AUTHENTICATION"]);
var text2 = (value) => typeof value === "string" ? value : "";
function placeholders(value) {
  return new Set([...value.matchAll(/\{\{\s*(\d+)\s*\}\}/g)].map((m4) => m4[1])).size;
}
function namedVariables(value) {
  const names = [...value.matchAll(/\{\{\s*([^{}]*?)\s*\}\}/g)].map((m4) => m4[1]);
  return [...new Set(names.filter((name) => !/^\d+$/.test(name)))];
}
function namedExamplesOf(body, variables) {
  let examples;
  try {
    examples = JSON.parse(variables);
  } catch {
    return {};
  }
  if (!Array.isArray(examples)) return {};
  const out = {};
  namedVariables(body).forEach((name, i7) => {
    if (i7 < examples.length) out[name] = String(examples[i7]);
  });
  return out;
}
function buttonsFromMeta(raw) {
  if (!Array.isArray(raw) || raw.length === 0) return null;
  const out = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") return null;
    const button = item;
    const type = text2(button.type).trim().toUpperCase();
    const label = text2(button.text).trim();
    if (!label) return null;
    if (type === "QUICK_REPLY") {
      out.push({ type, text: label });
    } else if (type === "URL") {
      const url = text2(button.url).trim();
      if (!url) return null;
      out.push({ type, text: label, url });
    } else if (type === "PHONE_NUMBER") {
      const phone = text2(button.phone_number).trim();
      if (!phone) return null;
      out.push({ type, text: label, phone_number: phone });
    } else {
      return null;
    }
  }
  return out;
}
function templateFromMeta(template) {
  const refused = { ok: false };
  const name = text2(template.name).trim();
  const language = text2(template.language).trim();
  const category = text2(template.category).trim().toUpperCase();
  const status = text2(template.status).trim();
  if (!name || !language || !status || !CATEGORIES.has(category)) return refused;
  if (!Array.isArray(template.components)) return refused;
  let header = "";
  let headerFormat = "TEXT";
  let buttons = [];
  let body = "";
  let footer = "";
  let examples = [];
  let named = [];
  for (const raw of template.components) {
    if (!raw || typeof raw !== "object") return refused;
    const part = raw;
    const type = text2(part.type).trim().toUpperCase();
    if (type === "HEADER") {
      const format = text2(part.format).trim().toUpperCase() || "TEXT";
      if (MEDIA_HEADERS.has(format)) {
        headerFormat = format;
        header = "";
      } else if (format === "TEXT") {
        header = text2(part.text);
        if (placeholders(header) > 0 || namedVariables(header).length > 0) return refused;
      } else {
        return refused;
      }
    } else if (type === "BODY") {
      body = text2(part.text);
      const example = part.example;
      const first = Array.isArray(example?.body_text) ? example.body_text[0] : void 0;
      examples = Array.isArray(first) ? first : [];
      named = Array.isArray(example?.body_text_named_params) ? example.body_text_named_params : [];
    } else if (type === "FOOTER") {
      footer = text2(part.text);
    } else if (type === "BUTTONS") {
      const read = buttonsFromMeta(part.buttons);
      if (!read) return refused;
      buttons = read;
    } else {
      return refused;
    }
  }
  if (!body.trim()) return refused;
  const names = namedVariables(body);
  let variables;
  if (names.length === 0) {
    variables = Array.from({ length: placeholders(body) }, (_2, i7) => text2(examples[i7]).trim() || `var${i7 + 1}`);
  } else {
    if (placeholders(body) > 0) return refused;
    const byName = /* @__PURE__ */ new Map();
    for (const item of named) {
      const param = item ?? {};
      const key = text2(param.param_name).trim();
      if (key && !byName.has(key)) byName.set(key, text2(param.example).trim());
    }
    variables = names.map((name2) => byName.get(name2) || name2);
  }
  return {
    ok: true,
    fields: {
      name,
      language,
      category,
      header,
      body,
      footer,
      variables: JSON.stringify(variables),
      header_format: headerFormat,
      buttons: JSON.stringify(buttons)
    },
    meta: {
      meta_template_id: text2(template.meta_id).trim(),
      meta_status: status,
      meta_rejected_reason: text2(template.rejected_reason)
    }
  };
}

// ui/components/erp-whatsapp-inbox-templates/erp-whatsapp-inbox-templates.ts
var CATALOG3 = { es: es_default, en: en_default };
function storedButtons(raw) {
  if (typeof raw !== "string" || !raw.trim()) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((b3) => !!b3 && typeof b3 === "object" && typeof b3.text === "string") : [];
  } catch {
    return [];
  }
}
var HEADER_MEDIA_LABEL = {
  IMAGE: "ui.headerMediaImage",
  VIDEO: "ui.headerMediaVideo",
  DOCUMENT: "ui.headerMediaDocument"
};
var BUTTON_LABEL = {
  QUICK_REPLY: "ui.buttonQuickReply",
  URL: "ui.buttonUrl",
  PHONE_NUMBER: "ui.buttonPhone"
};
var MAX_BUTTONS = 10;
var MAX_BUTTON_TEXT = 25;
function cleanButton(b3) {
  const text3 = typeof b3.text === "string" ? b3.text : "";
  if (b3.type === "URL") return { type: "URL", text: text3, url: typeof b3.url === "string" ? b3.url : "" };
  if (b3.type === "PHONE_NUMBER") {
    return { type: "PHONE_NUMBER", text: text3, phone_number: typeof b3.phone_number === "string" ? b3.phone_number : "" };
  }
  return { type: "QUICK_REPLY", text: text3 };
}
function groupedButtons(buttons) {
  if (!buttons.length) return [];
  const firstIsReply = buttons[0].type === "QUICK_REPLY";
  const replies = buttons.filter((b3) => b3.type === "QUICK_REPLY");
  const calls = buttons.filter((b3) => b3.type !== "QUICK_REPLY");
  return firstIsReply ? [...replies, ...calls] : [...calls, ...replies];
}
function metaKey(name, language) {
  const word = (value) => String(value ?? "").trim().toLowerCase();
  return `${word(name)}\0${word(language)}`;
}
function erplora3() {
  const c5 = globalThis.erplora;
  if (!c5) throw new Error("erplora SDK no inicializado por el shell");
  return c5;
}
function domainErrorText3(e5, fallbackKey) {
  const declared = domainErrorText(CATALOG3, erplora3().locale, e5);
  if (declared) return declared;
  return (e5 instanceof Error ? e5.message : "") || erplora3().t(CATALOG3, fallbackKey);
}
function metaStatusLabel(status) {
  const { labelKey } = metaTemplateView(status);
  return labelKey ? erplora3().t(CATALOG3, labelKey) : status;
}
var _ErpWhatsappInboxTemplates = class _ErpWhatsappInboxTemplates extends i3 {
  constructor() {
    super(...arguments);
    this.newName = "";
    this.newCategory = "UTILITY";
    this.newLanguage = "es";
    this.newBody = "";
    this.saving = false;
    this.formError = "";
    this.tick = 0;
    this.editingId = "";
    this.pendingDelete = null;
    this.metaSyncNotice = "";
    this.metaOnly = [];
    this.editingMeta = null;
    this.editingMetaCode = "";
    this.editingMetaReason = "";
    this.editingHeaderFormat = "TEXT";
    this.editingButtons = [];
    this.editingDynamicLink = false;
    /** The example Meta holds for each named variable of the template being edited, by name. Named
     *  templates store one example per distinct name in first-appearance order (whatsapp_inbox#186),
     *  so this is how the examples follow their NAME when the owner rewrites the body. */
    this.namedExamples = {};
    this.editingRest = {
      header: "",
      footer: "",
      variables: "[]",
      is_active: 1
    };
    this.onLocaleChange = () => this.requestUpdate();
  }
  static {
    this.styles = i`
    :host { display:flex; flex-direction:column; height:100%; min-height:0; font-family: system-ui, sans-serif; color: var(--ion-text-color, #1c1b18); }
    /* La vista llena el alto: el data-table ocupa el resto (scroll interno, pie fijo). */
    .page { display:flex; flex-direction:column; min-height:0; flex:1 1 auto; }
    .page > ok-data-table { flex:1 1 auto; min-height:0; }
    /* El alta va en el panel lateral de la tabla (estrecho) → columna, no fila. */
    .form { display:flex; flex-direction:column; gap:.7rem; }
    .form ion-button { align-self:flex-end; }
    .err { color:#d9480f; font-weight:600; }
    .panel { flex:0 0 auto; border:1px solid var(--ion-border-color,#e7e2d6);
      border-radius: var(--ok-radius-sm, 10px); padding:.75rem 1rem; margin:0 0 1rem;
      background:var(--ok-surface-2, var(--ion-color-step-50, rgba(0,0,0,.04))); }
    /* 44px minimum touch target: this screen is used one-handed, at a counter. */
    ion-button { --min-height: 44px; }
    /* pm#392 — the tone of a button is declared HERE, never with \`color="…"\`: Ionic resolves
       \`color=\` through a GLOBAL \`.ion-color-*\` rule that does not reach inside this shadow root,
       so a solid button came out as white text on a transparent background (invisible). Custom
       properties do inherit through the boundary, so the theme token still applies. */
    ion-button.tone-danger:not([fill]) {
      --background: var(--ion-color-danger, #c5000f);
      --background-activated: var(--ion-color-danger-shade, #ad000d);
      --background-focused: var(--ion-color-danger-shade, #ad000d);
      --background-hover: var(--ion-color-danger-tint, #cb1a27);
      --color: var(--ion-color-danger-contrast, #fff);
    }
    /* Meta's verdict: the colour is a second channel, never the only one — the sentence says it. */
    .meta { border-left: 4px solid var(--ok-color-medium, #8a8578); padding: .5rem .75rem;
      border-radius: var(--ok-radius-sm, 10px);
      background: var(--ok-surface-2, var(--ion-color-step-50, rgba(0,0,0,.04))); }
    .meta p { margin: .25rem 0 0; font-size: .9rem; }
    .meta[data-state="approved"] { border-left-color: var(--ion-color-success, #2dd36f); }
    .meta[data-state="rejected"],
    .meta[data-state="paused"],
    .meta[data-state="disabled"],
    .meta[data-state="deleted"] { border-left-color: var(--ion-color-danger, #c5000f); }
    /* What a template brought from WhatsApp Manager carries beyond its text (whatsapp_inbox#180). */
    .rich { display:flex; flex-direction:column; gap:.4rem; }
    .rich p { margin:0; font-size:.9rem; }
    .rich ul { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:.35rem; }
    .rich li { border:1px solid var(--ion-border-color,#e7e2d6); border-radius: var(--ok-radius-sm, 10px);
      padding:.4rem .6rem; font-size:.9rem; overflow-wrap:anywhere; }
    .rich li small { display:block; color: var(--ion-color-medium, #6b675d); }
    .button-row { display:flex; flex-direction:column; gap:.4rem; padding:.5rem;
      border:1px solid var(--ion-border-color,#e7e2d6); border-radius: var(--ok-radius-sm, 10px); }
    .button-row ion-button, .rich > ion-button { align-self:flex-start; }
  `;
  }
  /** Some parts of a template are still read-only here (whatsapp_inbox#180): «Guardar» registers
   *  the template again at Meta from what this panel holds, and this panel cannot write those parts
   *  yet — saving would strip them at Meta. A media header (whatsapp_inbox#218) and a link button
   *  with a variable, which needs an example and a value on every send, lock the panel; plain quick
   *  reply, link and call buttons do not since whatsapp_inbox#185, nor named body variables
   *  (`{{nombre}}`), which the SaaS registers as `parameter_format: NAMED` (saas#2281,
   *  whatsapp_inbox#196). It is edited in WhatsApp Manager and the tab brings Meta's verdict back
   *  on the next open. */
  get managedInMeta() {
    return !!this.editingId && (this.editingHeaderFormat !== "TEXT" || this.editingDynamicLink);
  }
  /** A button still missing its label, its link or its number: Meta would refuse the template. */
  get buttonsIncomplete() {
    return this.editingButtons.some(
      (b3) => !b3.text.trim() || "url" in b3 && !b3.url.trim() || "phone_number" in b3 && !b3.phone_number.trim()
    );
  }
  /** Adds an empty quick reply at the end, up to Meta's ten. */
  addButton() {
    if (this.editingButtons.length >= MAX_BUTTONS) return;
    this.editingButtons = [...this.editingButtons, { type: "QUICK_REPLY", text: "" }];
  }
  removeButton(index) {
    this.editingButtons = this.editingButtons.filter((_2, i7) => i7 !== index);
  }
  /** Changes one button. Changing its kind keeps the label and drops what the old kind carried: a
   *  link does not drag a phone number along to Meta. */
  setButton(index, patch) {
    this.editingButtons = this.editingButtons.map((b3, i7) => i7 === index ? cleanButton({ ...b3, ...patch }) : b3);
  }
  get rowActions() {
    const t5 = (k2) => erplora3().t(CATALOG3, k2);
    return [
      { id: "edit", label: t5("ui.edit"), icon: "create-outline", color: "primary" },
      { id: "delete", label: t5("ui.delete"), icon: "trash-outline", color: "danger" }
    ];
  }
  get columns() {
    const t5 = (k2) => erplora3().t(CATALOG3, k2);
    return [
      { key: "name", header: t5("ui.colName"), sortable: true, filterable: true, filterType: "text" },
      { key: "language", header: t5("ui.colLanguage"), sortable: true, filterable: true, filterType: "text" },
      {
        key: "category",
        header: t5("ui.colCategory"),
        sortable: true,
        filterable: true,
        filterType: "select",
        options: [
          { value: "UTILITY", label: t5("ui.categoryUtility") },
          { value: "MARKETING", label: t5("ui.categoryMarketing") },
          { value: "AUTHENTICATION", label: t5("ui.categoryAuthentication") }
        ]
      },
      {
        // Meta's verdict is a closed vocabulary and the server filters it by exact equality on the
        // value `queries/templates_list.sql` projects: typed by hand, «aprobado» would match no row.
        key: "meta_status",
        header: t5("ui.colMetaStatus"),
        sortable: true,
        filterable: true,
        filterType: "select",
        options: META_TEMPLATE_STATES.map((value) => ({ value, label: metaStatusLabel(value) })),
        format: (r6) => metaStatusLabel(String(r6.meta_status ?? ""))
      },
      {
        key: "is_active",
        header: t5("ui.colActive"),
        align: "right",
        sortable: true,
        filterable: true,
        filterType: "select",
        options: [
          { value: "1", label: t5("ui.yes") },
          { value: "0", label: t5("ui.no") }
        ],
        format: (r6) => Number(r6.is_active) ? t5("ui.yes") : t5("ui.no")
      }
    ];
  }
  // TODO-LIT: componentWillLoad → connectedCallback. Recuerda: connectedCallback se dispara
  // en CADA reconexión al DOM (no solo en el primer montaje). Si la init debe correr una
  // sola vez tras el primer render, considera firstUpdated() en su lugar.
  async connectedCallback() {
    super.connectedCallback();
    window.addEventListener("erplora:locale-changed", this.onLocaleChange);
    this.ctrl = createListController(erplora3(), "whatsapp_inbox.templates.list", () => this.requestUpdate(), {
      pageSize: 50,
      sort: "created_at",
      dir: "desc"
    });
    await this.ctrl.load();
    try {
      const offs = [
        erplora3().on("whatsapp_inbox.template.created", () => this.ctrl.load()),
        erplora3().on("whatsapp_inbox.template.updated", () => this.ctrl.load()),
        erplora3().on("whatsapp_inbox.template.deleted", () => this.ctrl.load())
      ];
      this.unsub = () => offs.forEach((o7) => o7());
    } catch {
    }
    await this.refreshMetaVerdicts();
  }
  /**
   * Put Meta's CURRENT verdict on the rows, once, as the tab opens (whatsapp_inbox#134).
   *
   * Meta answers a template minutes — sometimes hours — after it is sent, and until this existed
   * the answer never reached the tab: the row kept the verdict it had when it was saved, so a
   * template Meta had already approved went on reading «En revisión» and the owner had to go to
   * WhatsApp Manager to find out, which is the one errand this tab exists to save.
   *
   * 🔴 **On opening, NEVER on a timer.** The SaaS refreshes against Meta on every read of that door
   * and the path carries no throttle of its own (hub#1610, ERPlora/saas#1905): an interval here
   * would be one call to Meta per open tab per tick. `connectedCallback` is exactly «the tab
   * opened», and `tests/meta_refresh_is_not_a_poll.contract.test.py` is what keeps it that way.
   *
   * Nothing in here can cost the owner the list: every leg is guarded and the worst outcome is the
   * rows this hub already had, with a line saying they may have moved.
   */
  async refreshMetaVerdicts() {
    this.metaSyncNotice = "";
    this.metaOnly = [];
    let answer;
    let rows;
    try {
      answer = await erplora3().forModule("whatsapp_inbox").whatsappTemplates.list();
      rows = await erplora3().queryAll("whatsapp_inbox.templates.list");
    } catch {
      this.metaSyncNotice = erplora3().t(CATALOG3, "ui.metaSyncUnavailable");
      return;
    }
    if (answer?.stale === true) this.metaSyncNotice = erplora3().t(CATALOG3, "ui.metaSyncUnavailable");
    const atMeta = /* @__PURE__ */ new Map();
    const listed = Array.isArray(answer?.templates) ? answer.templates : [];
    for (const template of listed) atMeta.set(metaKey(template?.name, template?.language), template);
    const absenceIsDeletion = answer?.stale !== true && listed.length > 0;
    const text3 = (value) => typeof value === "string" ? value : "";
    let written = 0;
    for (const row of rows) {
      const answered = atMeta.get(metaKey(row.name, row.language));
      const knownId = text3(row.meta_template_id).trim();
      let verdict;
      if (answered) {
        verdict = answered;
      } else if (absenceIsDeletion && knownId) {
        verdict = { status: "DELETED", rejected_reason: "" };
      } else {
        continue;
      }
      const status = text3(verdict.status).trim();
      if (!status) continue;
      const metaId = text3(verdict.meta_id).trim() || text3(row.meta_template_id);
      const reason = text3(verdict.rejected_reason);
      const projected = metaId ? status.toLowerCase() : "not_sent";
      if (projected === text3(row.meta_status) && reason === text3(row.meta_rejected_reason) && metaId === text3(row.meta_template_id)) {
        continue;
      }
      try {
        await erplora3().command("whatsapp_inbox.templates.record_meta_answer", {
          template_id: row.id,
          meta_template_id: metaId,
          meta_status: status,
          meta_rejected_reason: reason,
          // The eight fields Meta reviewed travel with the answer: the command only writes if the
          // row still holds them, so a verdict never lands on a text the owner has since changed.
          name: row.name,
          language: row.language,
          category: row.category,
          header: row.header,
          body: row.body,
          footer: row.footer,
          variables: row.variables,
          // A row read before the column existed stores the column's default.
          buttons: row.buttons ?? "[]"
        });
        written += 1;
      } catch (e5) {
        this.metaSyncNotice = domainErrorText3(e5, "ui.errUpdateTemplate");
      }
    }
    const here = new Set(rows.map((row) => metaKey(row.name, row.language)));
    const notBrought = [];
    for (const template of listed) {
      if (!text3(template?.name).trim() || here.has(metaKey(template.name, template.language))) continue;
      here.add(metaKey(template.name, template.language));
      const label = `${text3(template.name).trim()} (${text3(template.language).trim()})`;
      const imported = templateFromMeta(template);
      if (!imported.ok) {
        notBrought.push(label);
        continue;
      }
      try {
        await erplora3().command("whatsapp_inbox.templates.import_from_meta", {
          ...imported.fields,
          ...imported.meta
        });
        written += 1;
      } catch (e5) {
        if (e5?.code === "whatsapp_inbox.template_already_here") continue;
        notBrought.push(label);
        this.metaSyncNotice = domainErrorText3(e5, "ui.errCreateTemplate");
      }
    }
    if (written) await this.ctrl.load();
    this.metaOnly = notBrought;
  }
  disconnectedCallback() {
    window.removeEventListener("erplora:locale-changed", this.onLocaleChange);
    super.disconnectedCallback();
    this.unsub?.();
  }
  // Referencia al ok-data-table para cerrar su panel lateral (el alta vive dentro).
  dataTable() {
    return this.renderRoot.querySelector("ok-data-table");
  }
  /** What the panel currently holds, in the shape Meta reviews it. */
  reviewedFields() {
    return {
      name: this.newName.trim(),
      language: this.newLanguage.trim() || "es",
      category: this.newCategory,
      header: this.editingRest.header,
      body: this.newBody,
      footer: this.editingRest.footer,
      variables: this.variablesFor(this.newBody),
      buttons: JSON.stringify(groupedButtons(this.editingButtons.map(cleanButton)))
    };
  }
  /** The examples the door must send with `body`. A NAMED body takes one example per distinct name,
   *  in the order the body first uses it — the SaaS pairs them by position (saas#2281): a name the
   *  body kept keeps its example, a name it dropped loses it, and a new one is its own example, the
   *  same way a numbered variable's name is its sample. A numbered body travels as it was. */
  variablesFor(body) {
    const names = namedVariables(body);
    if (!names.length) return this.editingRest.variables;
    return JSON.stringify(names.map((name) => this.namedExamples[name] ?? name));
  }
  /**
   * Register the template with Meta and put back what Meta answered (whatsapp_inbox#87).
   *
   * 🔴 **Called AFTER the local write, always.** Meta is a third party across the internet and the
   * template is the shop's: a Meta that does not answer costs a notice, never the owner's text.
   * That order is what whatsapp_inbox#65 could not have — before hub#1682 there was no door at
   * all, so the column said «pending» about a template nobody had ever sent.
   *
   * A refusal is SPOKEN, never echoed: the door answers a code (ADR-0055) and this module owns the
   * sentence. And a refusal never writes a verdict — the row stays `not_sent`, which is the truth.
   */
  async registerWithMeta(templateId, reviewed) {
    let verdict;
    try {
      verdict = await erplora3().forModule("whatsapp_inbox").whatsappTemplates.register({ ...reviewed });
    } catch (e5) {
      this.formError = doorRefusalText(CATALOG3, erplora3().locale, e5);
      return;
    }
    const text3 = (value) => typeof value === "string" ? value : "";
    const status = text3(verdict?.status).trim();
    if (!status || !templateId) {
      this.formError = doorRefusalText(CATALOG3, erplora3().locale, null);
      return;
    }
    try {
      await erplora3().command("whatsapp_inbox.templates.record_meta_answer", {
        template_id: templateId,
        meta_template_id: text3(verdict.meta_id),
        meta_status: status,
        meta_rejected_reason: text3(verdict.rejected_reason),
        ...reviewed
      });
    } catch (e5) {
      this.formError = domainErrorText3(e5, "ui.errUpdateTemplate");
    }
  }
  /** The id of the row a declarative create just inserted: the runtime answers `new_ids`, whose
   *  first entry is the main entity by convention (`hub: crates/runtime/src/commands.rs`). */
  static newId(result) {
    const ids = result?.new_ids;
    const first = Array.isArray(ids) ? ids[0] : void 0;
    return typeof first === "string" ? first : "";
  }
  async createTemplate(ev) {
    ev.preventDefault();
    if (!this.newName.trim() || this.managedInMeta || this.buttonsIncomplete) return;
    if (this.editingId) {
      await this.updateTemplate();
      return;
    }
    this.saving = true;
    this.formError = "";
    const reviewed = this.reviewedFields();
    try {
      const created = await erplora3().command("whatsapp_inbox.templates.create", reviewed);
      await this.registerWithMeta(_ErpWhatsappInboxTemplates.newId(created), reviewed);
      this.resetForm();
      this.dataTable()?.close();
      await this.ctrl.load();
    } catch (e5) {
      this.formError = e5 instanceof Error ? e5.message : erplora3().t(CATALOG3, "ui.errCreateTemplate");
    } finally {
      this.saving = false;
    }
  }
  /** Loads a row into the panel and turns it into an edit. */
  startEdit(row) {
    this.editingId = row.id;
    this.newName = row.name ?? "";
    this.newLanguage = row.language ?? "es";
    this.newCategory = row.category ?? "UTILITY";
    this.newBody = row.body ?? "";
    this.editingRest = {
      header: row.header ?? "",
      footer: row.footer ?? "",
      variables: row.variables ?? "[]",
      is_active: Number(row.is_active ?? 1)
    };
    this.editingHeaderFormat = String(row.header_format ?? "").trim().toUpperCase() || "TEXT";
    this.editingButtons = storedButtons(row.buttons).map(cleanButton);
    this.editingDynamicLink = this.editingButtons.some((b3) => "url" in b3 && b3.url.includes("{{"));
    this.namedExamples = namedExamplesOf(this.newBody, this.editingRest.variables);
    this.editingMeta = metaTemplateView(row.meta_status);
    this.editingMetaCode = String(row.meta_status ?? "");
    this.editingMetaReason = String(row.meta_rejected_reason ?? "");
    this.formError = "";
    this.dataTable()?.open("create");
  }
  /** Opens the panel as an ADD, on an empty form.
   *
   *  The «+» is dispatched by the MODULE (`primaryAction`) instead of being left to `addable`,
   *  for the reason appointments#42 found first: the panel is ONE — it is the add and it is the
   *  edit — and with `addable` the table opened it on its own, so the module never learnt about
   *  it. Closing a template with the scrim and pressing «+» next handed back the previous
   *  template: its name and body in the fields, its `editingId` (so «Add» saved an EDIT on top of
   *  it) and, since whatsapp_inbox#65, Meta's verdict ON ANOTHER TEMPLATE next to them. */
  async openCreate() {
    this.resetForm();
    this.formError = "";
    await this.updateComplete;
    this.dataTable()?.open("create");
  }
  resetForm() {
    this.editingId = "";
    this.newName = "";
    this.newBody = "";
    this.newLanguage = "es";
    this.newCategory = "UTILITY";
    this.editingRest = { header: "", footer: "", variables: "[]", is_active: 1 };
    this.editingButtons = [];
    this.editingDynamicLink = false;
    this.namedExamples = {};
    this.editingMeta = null;
    this.editingMetaCode = "";
    this.editingMetaReason = "";
  }
  cancelEdit() {
    this.resetForm();
    this.formError = "";
    this.dataTable()?.close();
  }
  /** `templates.update` requires EVERY field: what the panel does not show travels back unchanged
   *  (`editingRest`), so editing the body never silently blanks a header somebody set. */
  async updateTemplate() {
    this.saving = true;
    this.formError = "";
    const reviewed = this.reviewedFields();
    const templateId = this.editingId;
    try {
      await erplora3().command("whatsapp_inbox.templates.update", {
        template_id: templateId,
        ...reviewed,
        is_active: this.editingRest.is_active
      });
      await this.registerWithMeta(templateId, reviewed);
      this.resetForm();
      this.dataTable()?.close();
      await this.ctrl.load();
    } catch (e5) {
      this.formError = domainErrorText3(e5, "ui.errUpdateTemplate");
    } finally {
      this.saving = false;
    }
  }
  /** Deleting asks first, in the page — never `window.confirm`, which a POS webview swallows. Same
   *  in-page confirm panel `customers` uses for its tags. */
  async confirmDelete() {
    const row = this.pendingDelete;
    if (!row) return;
    this.saving = true;
    this.formError = "";
    try {
      await erplora3().command("whatsapp_inbox.templates.delete", { template_id: row.id });
      if (this.editingId === row.id) this.resetForm();
      this.pendingDelete = null;
      await this.ctrl.load();
    } catch (e5) {
      this.formError = domainErrorText3(e5, "ui.errDeleteTemplate");
    } finally {
      this.saving = false;
    }
  }
  onRowAction(ev) {
    const row = ev.detail.row;
    if (ev.detail.actionId === "edit") this.startEdit(row);
    if (ev.detail.actionId === "delete") {
      this.pendingDelete = row;
      this.formError = "";
    }
  }
  /** What Meta says about this template and what the owner has to do about it.
   *
   *  It lives in the panel, next to the fields that fix it, which is where every WhatsApp tool the
   *  market has (Meta's own WhatsApp Manager, Twilio, 360dialog, Brevo) puts it: the list carries
   *  the short state, the detail carries the move. A whole sentence per row would drown the table
   *  it is supposed to explain. */
  renderMetaVerdict() {
    if (!this.editingMeta) return A;
    const t5 = (k2) => erplora3().t(CATALOG3, k2);
    const { state, labelKey, actionKey } = this.editingMeta;
    return b2`<div class="meta" data-testid="whatsapp-templates-meta-verdict" data-state=${state}>
      <strong>${t5("ui.colMetaStatus")}: ${labelKey ? t5(labelKey) : this.editingMetaCode}</strong>
      <p>${t5(actionKey)}</p>
      ${this.editingMetaReason ? b2`<p>${erplora3().t(CATALOG3, "ui.metaRejectedReason", { reason: this.editingMetaReason })}</p>` : A}
    </div>`;
  }
  /** The media header and the buttons of a template brought from WhatsApp Manager, and why its
   *  text is not saved from here (whatsapp_inbox#180). Nothing for a text-only template. */
  renderRichParts() {
    if (!this.managedInMeta) return A;
    const t5 = (k2) => erplora3().t(CATALOG3, k2);
    const media = HEADER_MEDIA_LABEL[this.editingHeaderFormat];
    return b2`<div class="rich">
      ${media ? b2`<p data-testid="whatsapp-templates-header-media" data-format=${this.editingHeaderFormat}>${t5(media)}</p>` : A}
      ${this.editingButtons.length ? b2`<strong>${t5("ui.templateButtons")}</strong>
            <ul>
              ${this.editingButtons.map(
      (b3) => b2`<li data-testid="whatsapp-templates-button" data-type=${b3.type}>
                  ${b3.text}
                  <small>${t5(BUTTON_LABEL[b3.type] ?? "ui.buttonQuickReply")}${"url" in b3 ? b2` · ${b3.url}` : A}${"phone_number" in b3 ? b2` · ${b3.phone_number}` : A}</small>
                </li>`
    )}
            </ul>` : A}
      <p data-testid="whatsapp-templates-managed-in-meta">${t5("ui.templateManagedInMeta")}</p>
    </div>`;
  }
  /** The buttons editor (whatsapp_inbox#185): kind, label and — for a link or a call — where it
   *  goes. Nothing while the panel is read-only: `renderRichParts` lists them instead. */
  renderButtonsEditor() {
    if (this.managedInMeta) return A;
    const t5 = (k2) => erplora3().t(CATALOG3, k2);
    return b2`<div class="rich" data-testid="whatsapp-templates-buttons">
      <strong>${t5("ui.templateButtons")}</strong>
      <p>${t5("ui.buttonsHint")}</p>
      ${this.editingButtons.map(
      (b3, i7) => b2`<div class="button-row" data-testid="whatsapp-templates-button-row" data-type=${b3.type}>
          <ion-select data-testid="whatsapp-templates-button-type" mode="md" fill="outline" label-placement="floating"
            label=${t5("ui.buttonType")} .value=${b3.type} @ionChange=${(e5) => this.setButton(i7, { type: e5.target.value })}>
            <ion-select-option value="QUICK_REPLY">${t5("ui.buttonQuickReply")}</ion-select-option>
            <ion-select-option value="URL">${t5("ui.buttonUrl")}</ion-select-option>
            <ion-select-option value="PHONE_NUMBER">${t5("ui.buttonPhone")}</ion-select-option>
          </ion-select>
          <ion-input data-testid="whatsapp-templates-button-text" mode="md" fill="outline" label-placement="floating"
            label=${t5("ui.buttonText")} maxlength=${MAX_BUTTON_TEXT} counter .value=${b3.text}
            @ionInput=${(e5) => this.setButton(i7, { text: e5.target.value ?? "" })}></ion-input>
          ${"url" in b3 ? b2`<ion-input data-testid="whatsapp-templates-button-url" type="url" inputmode="url" mode="md" fill="outline"
                label-placement="floating" label=${t5("ui.buttonUrlField")} placeholder="https://" .value=${b3.url}
                @ionInput=${(e5) => this.setButton(i7, { url: e5.target.value ?? "" })}></ion-input>` : A}
          ${"phone_number" in b3 ? b2`<ion-input data-testid="whatsapp-templates-button-phone" type="tel" inputmode="tel" mode="md" fill="outline"
                label-placement="floating" label=${t5("ui.buttonPhoneField")} placeholder="+34600111222" .value=${b3.phone_number}
                @ionInput=${(e5) => this.setButton(i7, { phone_number: e5.target.value ?? "" })}></ion-input>` : A}
          <ion-button data-testid="whatsapp-templates-button-remove" fill="clear" size="small"
            @click=${() => this.removeButton(i7)}>${t5("ui.removeButton")}</ion-button>
        </div>`
    )}
      <ion-button data-testid="whatsapp-templates-button-add" fill="outline" size="small"
        ?disabled=${this.editingButtons.length >= MAX_BUTTONS} @click=${() => this.addButton()}>${t5("ui.addButton")}</ion-button>
    </div>`;
  }
  renderDeleteConfirm() {
    if (!this.pendingDelete) return A;
    const t5 = (k2) => erplora3().t(CATALOG3, k2);
    return b2`<section class="panel">
      <p>${t5("ui.confirmDeleteTemplate")} <strong>${this.pendingDelete.name}</strong></p>
      <ion-button data-testid="whatsapp-templates-delete-confirm" size="small" class="tone-danger" ?disabled=${this.saving}
        @click=${() => this.confirmDelete()}>${t5("ui.delete")}</ion-button>
      <ion-button data-testid="whatsapp-templates-delete-cancel" size="small" fill="clear" @click=${() => this.pendingDelete = null}>${t5("ui.cancel")}</ion-button>
    </section>`;
  }
  render() {
    const t5 = (k2) => erplora3().t(CATALOG3, k2);
    const locked = this.managedInMeta;
    return b2`<div class="page">
        ${this.formError ? b2`<p class="err" data-testid="whatsapp-templates-form-error">${this.formError}</p>` : A}
        ${this.ctrl?.error ? b2`<p class="err" data-testid="whatsapp-templates-load-error">${this.ctrl.error}</p>` : A}
        ${this.metaSyncNotice ? b2`<section class="panel"><p data-testid="whatsapp-templates-meta-sync-notice">${this.metaSyncNotice}</p></section>` : A}
        ${this.metaOnly.length ? b2`<section class="panel"><p data-testid="whatsapp-templates-meta-only">${erplora3().t(CATALOG3, "ui.metaOnlyTemplates", { names: this.metaOnly.join(", ") })}</p></section>` : A}
        ${this.renderDeleteConfirm()}
        <ok-data-table testid="whatsapp-templates-table" .serverSide=${true} .fill=${true} .primaryAction=${{ label: t5("ui.add"), icon: "add" }} @primaryAction=${() => this.openCreate()} .views=${true} .actions=${this.rowActions} .rowClickable=${true} .cardTitle=${(row) => String(row.name ?? "\u2014")} .columns=${this.columns} .rows=${this.ctrl?.rows ?? []} .total=${this.ctrl?.total ?? 0} .page=${this.ctrl?.state.page ?? 0} .pageSize=${this.ctrl?.state.pageSize ?? 50} .sort=${this.ctrl?.state.sort} .sortDir=${this.ctrl?.state.dir ?? "desc"} .searchable=${true} .searchPlaceholder=${t5("ui.searchTemplates")} .emptyMessage=${this.ctrl?.loading ? t5("ui.loading") : t5("ui.emptyTemplates")} @rowAction=${(e5) => this.onRowAction(e5)} @rowClick=${(e5) => this.onRowAction({ detail: { actionId: "edit", row: e5.detail.row } })} @pageChange=${(e5) => this.ctrl.setPage(e5.detail)} @pageSizeChange=${(e5) => this.ctrl.setPageSize(e5.detail)} @sortChange=${(e5) => this.ctrl.setSort(e5.detail.sort, e5.detail.dir)} @searchChange=${(e5) => this.ctrl.setSearch(e5.detail)} @filterChange=${(e5) => this.ctrl.setFilter(e5.detail.col, e5.detail.value)}>
          <!-- Alta: se proyecta SIEMPRE (aunque el panel esté cerrado). Si solo se renderizara con el
               panel abierto, el «+» de la barra desplegaría un panel vacío. -->
          <form data-testid="whatsapp-templates-form" slot="create" class="form" @submit=${(e5) => this.createTemplate(e5)}>
            ${this.renderMetaVerdict()}
            ${this.renderRichParts()}
            <ion-input data-testid="whatsapp-templates-name" .disabled=${locked} mode="md" fill="outline" label-placement="floating" label=${t5("ui.colName")} .value=${this.newName} @ionInput=${(e5) => this.newName = e5.target.value}></ion-input>
            <ion-input data-testid="whatsapp-templates-language" .disabled=${locked} mode="md" fill="outline" label-placement="floating" label=${t5("ui.colLanguage")} placeholder=${t5("ui.placeholderLanguage")} .value=${this.newLanguage} @ionInput=${(e5) => this.newLanguage = e5.target.value}></ion-input>
            <ion-select data-testid="whatsapp-templates-category" .disabled=${locked} mode="md" fill="outline" label-placement="floating" label=${t5("ui.colCategory")} .value=${this.newCategory} @ionChange=${(e5) => this.newCategory = e5.target.value}>
              <ion-select-option value="UTILITY">${t5("ui.categoryUtility")}</ion-select-option>
              <ion-select-option value="MARKETING">${t5("ui.categoryMarketing")}</ion-select-option>
              <ion-select-option value="AUTHENTICATION">${t5("ui.categoryAuthentication")}</ion-select-option>
            </ion-select>
            <ion-textarea data-testid="whatsapp-templates-body" .disabled=${locked} mode="md" fill="outline" label-placement="floating" label=${t5("ui.colBody")} placeholder=${t5("ui.placeholderBody")} .value=${this.newBody} @ionInput=${(e5) => this.newBody = e5.target.value}></ion-textarea>
            ${this.renderButtonsEditor()}
            ${locked ? A : b2`<ion-button data-testid="whatsapp-templates-submit" type="submit" ?disabled=${this.saving || !this.newName || this.buttonsIncomplete}>${this.saving ? t5("ui.saving") : this.editingId ? t5("ui.save") : t5("ui.add")}</ion-button>`}
            ${this.editingId ? b2`<ion-button data-testid="whatsapp-templates-cancel" fill="clear" size="small" ?disabled=${this.saving}
                  @click=${() => this.cancelEdit()}>${t5("ui.cancel")}</ion-button>` : A}
          </form>
        </ok-data-table>
      </div>`;
  }
};
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "newName", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "newCategory", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "newLanguage", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "newBody", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "saving", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "formError", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "tick", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "editingId", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "pendingDelete", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "metaSyncNotice", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "metaOnly", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "editingMeta", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "editingMetaCode", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "editingMetaReason", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "editingHeaderFormat", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "editingButtons", 2);
__decorateClass([
  r5()
], _ErpWhatsappInboxTemplates.prototype, "editingDynamicLink", 2);
var ErpWhatsappInboxTemplates = _ErpWhatsappInboxTemplates;
define("erp-whatsapp-inbox-templates", ErpWhatsappInboxTemplates);
