"use client"

import * as React from "react"
import { useReducedMotion } from "motion/react"

import { cn } from "@/lib/utils"

/**
 * Port of the educalvolpz "liquid-metal" (21st.dev): a full-cover WebGL2
 * liquid-chrome surface from domain-warped fbm noise. Chrome palette only, and
 * the pointer influence is removed so it never reacts to the mouse. Under
 * reduced motion it draws a single still frame; without WebGL2 it renders
 * nothing, so the page background shows through.
 */
export interface LiquidMetalProps extends React.ComponentProps<"div"> {
  /** Flow speed multiplier. */
  speed?: number
  /** Domain-warp strength, 0 to 3. */
  distortion?: number
  /**
   * 0 to 1: how much chrome shows over the page background (#0a0c0e). Mixed in the
   * shader rather than with CSS opacity, so the compositor has no extra layer to blend.
   */
  intensity?: number
}

/** Fraction of CSS pixels the shader renders at. */
const RENDER_SCALE = 0.5

const VERTEX = `#version 300 es
in vec2 a;
void main(){ gl_Position = vec4(a, 0.0, 1.0); }`

const FRAGMENT = `#version 300 es
precision highp float;
out vec4 fragColor;
uniform vec2 uRes;
uniform float uTime;
uniform float uDistortion;
uniform float uIntensity;

float hash(vec2 p){
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float noise(vec2 p){
  vec2 i = floor(p);
  vec2 f = fract(p);
  float a = hash(i);
  float b = hash(i + vec2(1.0, 0.0));
  float c = hash(i + vec2(0.0, 1.0));
  float d = hash(i + vec2(1.0, 1.0));
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

float fbm(vec2 p){
  float value = 0.0;
  float amplitude = 0.5;
  mat2 turn = mat2(1.6, 1.2, -1.2, 1.6);
  for (int i = 0; i < 4; i++){
    value += amplitude * noise(p);
    p = turn * p;
    amplitude *= 0.5;
  }
  return value;
}

void main(){
  vec2 uv = gl_FragCoord.xy / uRes;
  vec2 aspect = vec2(uRes.x / uRes.y, 1.0);
  vec2 p = (uv - 0.5) * aspect * 2.2;
  float warp = clamp(uDistortion, 0.0, 3.0);

  vec2 q = vec2(fbm(p), fbm(p + vec2(5.2, 1.3)));
  vec2 flow = p + warp * 3.2 * q;
  vec2 r = vec2(
    fbm(flow + vec2(1.7, 9.2) + uTime * 0.17),
    fbm(flow + vec2(8.3, 2.8) - uTime * 0.13)
  );

  vec2 base = p + warp * 2.8 * r;
  float eps = 0.006;
  float h = fbm(base);
  float hx = fbm(base + vec2(eps, 0.0));
  float hy = fbm(base + vec2(0.0, eps));
  vec3 n = normalize(vec3((h - hx) / eps * 0.05, (h - hy) / eps * 0.05, 1.0));

  vec3 view = normalize(vec3((uv - 0.5) * aspect, 1.0));
  vec3 refl = reflect(view, n);
  float f = clamp(refl.y * 0.5 + 0.5, 0.0, 1.0);
  float sideways = clamp(refl.x * 0.5 + 0.5, 0.0, 1.0);

  vec3 lo = vec3(0.04, 0.05, 0.07);
  vec3 hi = vec3(0.90, 0.94, 0.99);
  vec3 tint = vec3(0.58, 0.68, 0.85);

  vec3 col = mix(lo, hi, smoothstep(0.04, 0.96, f));
  col = mix(col, tint, pow(sideways, 2.0) * 0.55);

  float spec = pow(max(dot(n, normalize(vec3(0.35, 0.75, 0.55))), 0.0), 42.0);
  float fresnel = pow(1.0 - clamp(n.z, 0.0, 1.0), 3.0);
  col += spec * 0.85 + fresnel * 0.20;

  col = mix(vec3(0.039, 0.047, 0.055), clamp(col, 0.0, 1.0), uIntensity);
  fragColor = vec4(col, 1.0);
}`

export function LiquidMetal({ speed = 1, distortion = 1, intensity = 1, className, ...rest }: LiquidMetalProps) {
  const reduce = useReducedMotion()
  const canvasRef = React.useRef<HTMLCanvasElement>(null)

  React.useEffect(() => {
    const canvas = canvasRef.current
    const gl = canvas?.getContext("webgl2", { alpha: false, antialias: false, powerPreference: "low-power" })
    if (!canvas || !gl) return

    const compile = (type: number, src: string) => {
      const s = gl.createShader(type)!
      gl.shaderSource(s, src)
      gl.compileShader(s)
      return s
    }
    const vs = compile(gl.VERTEX_SHADER, VERTEX)
    const fs = compile(gl.FRAGMENT_SHADER, FRAGMENT)
    const program = gl.createProgram()!
    gl.attachShader(program, vs)
    gl.attachShader(program, fs)
    gl.linkProgram(program)
    gl.deleteShader(vs)
    gl.deleteShader(fs)
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      gl.deleteProgram(program)
      return
    }
    gl.useProgram(program)

    const buffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW)
    const position = gl.getAttribLocation(program, "a")
    gl.enableVertexAttribArray(position)
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0)

    const uRes = gl.getUniformLocation(program, "uRes")
    const uTime = gl.getUniformLocation(program, "uTime")
    gl.uniform1f(gl.getUniformLocation(program, "uDistortion"), distortion)
    gl.uniform1f(gl.getUniformLocation(program, "uIntensity"), intensity)

    // The surface is soft, so it renders at a fraction of CSS size and the browser upscales it.
    const resize = () => {
      canvas.width = Math.max(1, Math.round(canvas.clientWidth * RENDER_SCALE))
      canvas.height = Math.max(1, Math.round(canvas.clientHeight * RENDER_SCALE))
      gl.viewport(0, 0, canvas.width, canvas.height)
      gl.uniform2f(uRes, canvas.width, canvas.height)
    }

    let time = 0
    let last = performance.now()
    let frame = 0
    const draw = () => {
      gl.uniform1f(uTime, time)
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)
    }
    const tick = (now: number) => {
      frame = requestAnimationFrame(tick)
      // Clamp the step so a backgrounded tab does not jump the flow on return.
      time += Math.min((now - last) / 1000, 1 / 20) * speed
      last = now
      draw()
    }

    const ro = new ResizeObserver(() => {
      resize()
      draw()
    })
    ro.observe(canvas)
    resize()
    draw()
    if (!reduce) frame = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(frame)
      ro.disconnect()
      gl.deleteBuffer(buffer)
      gl.deleteProgram(program)
    }
  }, [reduce, speed, distortion, intensity])

  return (
    <div className={cn("absolute inset-0 overflow-hidden", className)} {...rest}>
      <canvas ref={canvasRef} className="block h-full w-full" />
    </div>
  )
}

export default LiquidMetal
