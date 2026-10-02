# Shader banner (preview)

Source for `preview-assets/shader-banner.js`, the animated ShaderGradient background on the
"Let's work together" banner in `preview-glass.html`.

Rebuild:

```sh
npm i @shadergradient/react@2.4.20 react@18 react-dom@18 three @react-three/fiber@8 esbuild
npx esbuild entry.jsx --bundle --minify --format=iife --jsx=automatic \
  --define:process.env.NODE_ENV='"production"' --outfile=../../preview-assets/shader-banner.js
```

ShaderGradient is MIT licensed. The bundle is about 1.2 MB (about 320 KB gzipped).
