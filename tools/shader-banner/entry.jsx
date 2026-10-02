// Animated ShaderGradient background for the "Let's work together" banner.
// Mounts into any element marked data-shader-bg; the CSS gradient underneath stays as the fallback.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { ShaderGradientCanvas, ShaderGradient } from '@shadergradient/react';

const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function hasWebGL() {
  try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch (e) { return false; }
}

function Banner() {
  return (
    <ShaderGradientCanvas style={{ position: 'absolute', inset: 0 }} pixelDensity={1} fov={45} pointerEvents="none">
      <ShaderGradient
        type="plane" animate={reduceMotion ? 'off' : 'on'} uTime={0.2}
        uSpeed={0.25} uStrength={2.6} uDensity={1.2} uFrequency={5.5} uAmplitude={1}
        color1="#ffb05a" color2="#f1907f" color3="#e8a0a6"
        brightness={1.15} grain="off" lightType="3d" reflection={0.1}
        cAzimuthAngle={180} cPolarAngle={90} cDistance={1.9} cameraZoom={1}
        positionX={-0.4} positionY={0} positionZ={0} rotationX={0} rotationY={10} rotationZ={40}
      />
    </ShaderGradientCanvas>
  );
}

function mount() {
  const el = document.querySelector('[data-shader-bg]');
  if (!el) return false;
  if (el.dataset.mounted) return true;
  el.dataset.mounted = '1';
  createRoot(el).render(<Banner />);
  requestAnimationFrame(() => el.classList.add('is-ready'));
  return true;
}

if (hasWebGL()) {
  // The page renders its markup after load, so wait for the banner to appear.
  if (!mount()) {
    const obs = new MutationObserver(() => { if (mount()) obs.disconnect(); });
    obs.observe(document.documentElement, { childList: true, subtree: true });
  }
}
