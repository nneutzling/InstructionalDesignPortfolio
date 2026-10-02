/*!
 * dc-runtime.js
 *
 * A small, dependency-free runtime that reproduces just enough of the
 * templating behavior these two pages were originally built with, so they
 * can run as plain static HTML/CSS/JS with no external framework.
 *
 * Supports, exactly as used in these two pages:
 *   - {{dotted.path}} interpolation inside text nodes and attribute values
 *   - <sc-for list="{{arrayExpr}}" as="item">...template...</sc-for>
 *   - <sc-if value="{{boolExpr}}">...</sc-if>
 *   - Event-handler attributes (data-onclick, data-onpointerdown, etc, see
 *     EVENT_ATTRS) whose value is a single {{handlerName}} hole resolving
 *     to a function
 *   - A DCLogic base class providing this.state / this.setState() /
 *     this.props, calling renderVals() to produce the data used above, and
 *     invoking componentDidMount() once after the first render.
 *
 * Re-rendering walks the live template tree RECURSIVELY and stops
 * descending the moment it hits an <sc-for> or <sc-if> -- those two
 * elements own and rebind their own subtree completely themselves. This
 * matters: an earlier version used a flat TreeWalker that pre-collected
 * every descendant node up front, including sc-for/sc-if's children: on a
 * second render those stale collected nodes got reprocessed a second time
 * by the outer pass using the wrong (non-item) scope, silently corrupting
 * or wiping already-correct bindings. Recursing and pruning at sc-for/
 * sc-if avoids that class of bug entirely.
 */
(function (global) {
  'use strict';

  function getPath(scope, path) {
    var parts = path.trim().split('.');
    var cur = scope;
    for (var i = 0; i < parts.length; i++) {
      if (cur == null) return undefined;
      cur = cur[parts[i]];
    }
    return cur;
  }

  function resolveTemplateString(str, scope) {
    // Whole-value hole (e.g. an attribute that is ONLY "{{x}}") resolves to
    // the raw value (so booleans/functions/numbers survive intact).
    var wholeMatch = str.match(/^\{\{\s*([^}]+?)\s*\}\}$/);
    if (wholeMatch) {
      return getPath(scope, wholeMatch[1]);
    }
    // Mixed text ("left: {{x}}%;") -> string interpolation.
    return str.replace(/\{\{\s*([^}]+?)\s*\}\}/g, function (_, path) {
      var v = getPath(scope, path);
      return v == null ? '' : String(v);
    });
  }

  function containsHole(str) {
    return typeof str === 'string' && str.indexOf('{{') !== -1;
  }

  // NOTE: these are deliberately "data-on*", not bare "onClick"/"onKeyDown".
  // HTML treats onclick/onkeydown/onpointerdown/etc as native, reserved,
  // CASE-INSENSITIVE attributes: the browser itself compiles their string
  // value into an inline handler the moment the element is parsed -- before
  // any of our own JS runs. An attribute like onClick="{{doThing}}" would
  // make the browser try to literally execute "{{doThing}}" as JavaScript
  // and throw. The conversion script rewrites the original onClick/onKeyDown
  // etc. attributes to these data-on* names so the browser leaves them
  // alone and only this runtime interprets them.
  var EVENT_ATTRS = {
    'data-onclick': 'click',
    'data-onpointerdown': 'pointerdown',
    'data-onpointermove': 'pointermove',
    'data-onpointerup': 'pointerup',
    'data-onpointerleave': 'pointerleave',
    'data-onpointercancel': 'pointercancel',
    'data-onkeydown': 'keydown'
  };

  // Bind a single element's own event-handler and plain attributes (not its
  // children). Safe to call repeatedly on the same live node.
  function bindElement(node, scope) {
    Object.keys(EVENT_ATTRS).forEach(function (attrName) {
      if (node.hasAttribute(attrName)) {
        var expr = node.getAttribute(attrName);
        var handler = resolveTemplateString(expr, scope);
        var domEvent = EVENT_ATTRS[attrName];
        if (typeof handler === 'function') {
          if (node.__dcHandlers && node.__dcHandlers[domEvent]) {
            node.removeEventListener(domEvent, node.__dcHandlers[domEvent]);
          }
          node.__dcHandlers = node.__dcHandlers || {};
          node.__dcHandlers[domEvent] = handler;
          node.addEventListener(domEvent, handler);
        }
      }
    });

    // Plain attribute interpolation (style, class, src, href, aria-*, etc).
    // node.attributes is a LIVE NamedNodeMap: removing an attribute (for a
    // false/null hole) while iterating it by index shifts every later
    // attribute's index down, silently skipping whichever one came right
    // after it. Snapshot first to avoid that.
    var attrSnapshot = Array.prototype.slice.call(node.attributes);
    for (var i = 0; i < attrSnapshot.length; i++) {
      var attr = attrSnapshot[i];
      if (attr.name in EVENT_ATTRS) continue;
      var key = '__dcAttr_' + attr.name;
      var template = node[key] != null ? node[key] : attr.value;
      if (containsHole(template)) {
        if (node[key] == null) node[key] = template;
        var resolved = resolveTemplateString(template, scope);
        if (resolved == null || resolved === false) {
          node.removeAttribute(attr.name);
        } else if (resolved === true) {
          node.setAttribute(attr.name, '');
        } else {
          node.setAttribute(attr.name, resolved);
        }
      }
    }
  }

  function bindText(node) {
    if (node.__dcTemplate == null) {
      if (!containsHole(node.nodeValue)) return false;
      node.__dcTemplate = node.nodeValue;
    }
    return true;
  }

  // The core recursive walker. Binds `node` itself, then recurses into its
  // children UNLESS node is <sc-for> or <sc-if>, which own their own
  // subtree and are never descended into by the generic pass.
  function bindSubtree(node, scope) {
    if (node.nodeType === Node.TEXT_NODE) {
      if (bindText(node)) {
        node.nodeValue = resolveTemplateString(node.__dcTemplate, scope);
      }
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;

    var tag = node.tagName;
    if (tag === 'SC-FOR') {
      renderScFor(node, scope);
      return;
    }
    if (tag === 'SC-IF') {
      renderScIf(node, scope);
      return;
    }

    bindElement(node, scope);

    // Snapshot childNodes before recursing: sc-for/sc-if below this node
    // may rewrite their own children, but never this node's direct
    // children list structurally (only text/element children we're about
    // to visit one at a time), so a static copy is just a safety measure.
    var children = Array.prototype.slice.call(node.childNodes);
    for (var i = 0; i < children.length; i++) {
      bindSubtree(children[i], scope);
    }
  }

  function renderScFor(scNode, outerScope) {
    if (!scNode.__dcTemplateHTML) {
      scNode.__dcTemplateHTML = scNode.innerHTML;
      scNode.innerHTML = '';
      scNode.style.display = 'contents';
    }
    var listExpr = scNode.getAttribute('list');
    var asName = scNode.getAttribute('as') || 'item';
    var list = resolveTemplateString(listExpr, outerScope);
    if (!Array.isArray(list)) list = [];

    scNode.__dcItems = scNode.__dcItems || [];

    // Remove extra clones if the list shrank.
    while (scNode.__dcItems.length > list.length) {
      var extra = scNode.__dcItems.pop();
      extra.forEach(function (elNode) {
        if (elNode.parentNode) elNode.parentNode.removeChild(elNode);
      });
    }

    list.forEach(function (item, i) {
      var scope = {};
      for (var k in outerScope) scope[k] = outerScope[k];
      scope[asName] = item;

      var group = scNode.__dcItems[i];
      if (!group) {
        var temp = document.createElement('div');
        temp.innerHTML = scNode.__dcTemplateHTML;
        group = [];
        while (temp.firstChild) {
          var child = temp.firstChild;
          temp.removeChild(child);
          scNode.appendChild(child);
          group.push(child);
        }
        scNode.__dcItems[i] = group;
      }

      // Re-bind this item's clone(s) with the item-scoped data every render
      // (first render and all subsequent ones alike), via the same
      // recursive walker used everywhere else.
      group.forEach(function (elNode) {
        bindSubtree(elNode, scope);
      });
    });
  }

  function renderScIf(scNode, scope) {
    if (!scNode.__dcTemplateHTML) {
      scNode.__dcTemplateHTML = scNode.innerHTML;
      scNode.innerHTML = '';
      var wrapper = document.createElement('div');
      wrapper.style.display = 'contents';
      wrapper.innerHTML = scNode.__dcTemplateHTML;
      scNode.__dcWrapper = wrapper;
      scNode.appendChild(wrapper);
    }
    var valExpr = scNode.getAttribute('value');
    var val = resolveTemplateString(valExpr, scope);
    scNode.__dcWrapper.style.display = val ? 'contents' : 'none';
    if (val) bindSubtree(scNode.__dcWrapper, scope);
  }

  // ---- DCLogic base class ----
  function DCLogic(props) {
    this.props = props || {};
    this.state = {};
    this.__dcRoot = null;
    this.__dcMounted = false;
  }
  DCLogic.prototype.setState = function (patch) {
    for (var k in patch) this.state[k] = patch[k];
    this.__dcRender();
  };
  DCLogic.prototype.__dcRender = function () {
    if (!this.__dcRoot) return;
    var data = this.renderVals();
    bindSubtree(this.__dcRoot, data);
    if (!this.__dcMounted) {
      this.__dcMounted = true;
      if (typeof this.componentDidMount === 'function') this.componentDidMount();
    }
  };

  // Mounts a Component class onto a root element. defaultProps comes from
  // the original data-props JSON's ".default" values.
  function mount(ComponentClass, rootEl, defaultProps) {
    var instance = new ComponentClass(defaultProps);
    instance.__dcRoot = rootEl;
    instance.__dcRender();
    return instance;
  }

  global.DCRuntime = { DCLogic: DCLogic, mount: mount };
  global.DCLogic = DCLogic; // so "class Component extends DCLogic" needs no edits
})(window);
