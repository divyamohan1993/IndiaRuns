"use client";

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { Funnel } from "@/lib/contracts";

/**
 * WebGL particle funnel — the heart of the Ranking Cinema. Instanced points
 * (drei-style buffer geometry) representing the candidate pool, animated across
 * four acts:
 *
 *   Act 0 — the pool (N points laid out in a soft cloud; rank-1..100 seeded by
 *            funnel.projection so the real top candidates are real positions).
 *   Act 1 — ignite to the ~1,198 shortlist (a scan line sweeps; outsiders dim).
 *   Act 2 — Trap Burn (the clean-201 honeypots flash red and fall away).
 *   Act 3 — crystallize: top 100 → top 10 converge to the center.
 *
 * Point count is GPU-tiered by the caller (`count`). Every burning point maps to
 * a real flagged candidate via the seeded RNG order, and the top-100 points are
 * the real projection coordinates. This is presentational — the ranking itself
 * is frozen in the artifacts.
 */

type Props = {
  funnel: Funnel;
  /** 0..3 act index, fractional during transitions. */
  act: number;
  /** total simulated points (GPU-tiered). */
  count: number;
};

const COL_POOL = new THREE.Color("#6E8BFF");
const COL_SHORT = new THREE.Color("#5BE0E6");
const COL_TRAP = new THREE.Color("#FF5C6C");
const COL_TOP = new THREE.Color("#F5C04E");

function seededRand(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function Points({ funnel, act, count }: Props) {
  const ref = useRef<THREE.Points>(null);
  const matRef = useRef<THREE.PointsMaterial>(null);

  // Build the static buffers once. Each point gets:
  //  - a "pool" position (cloud), a "center" target, a category, and a phase.
  const { geometry, meta } = useMemo(() => {
    const rand = seededRand(20260627);
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);

    // Fractions of the pool, mirrored from the real funnel counts.
    const total = funnel.stages[0]?.count ?? 100000;
    const trapFrac = funnel.honeypot_burn.total / total; // ~0.002
    const shortFrac =
      (funnel.stages.find((s) => /shortlist/i.test(s.name))?.count ?? 1226) /
      total; // ~0.012
    const topFrac = 100 / total;

    const proj = funnel.projection; // 100 real top positions
    const cat = new Uint8Array(count); // 0 pool,1 short,2 trap,3 top100,4 top10
    const targets = new Float32Array(count * 3);

    for (let i = 0; i < count; i++) {
      const u = i / count;
      // Pool layout: a disc with depth, organic.
      const ang = rand() * Math.PI * 2;
      const rad = Math.sqrt(rand()) * 6.5;
      const px = Math.cos(ang) * rad;
      const py = (rand() - 0.5) * 3.5;
      const pz = Math.sin(ang) * rad - 2;
      positions[i * 3] = px;
      positions[i * 3 + 1] = py;
      positions[i * 3 + 2] = pz;

      // Category assignment using the real fractions.
      let c = 0;
      if (u < topFrac) c = u < topFrac * 0.1 ? 4 : 3;
      else if (u < topFrac + trapFrac) c = 2;
      else if (u < topFrac + trapFrac + shortFrac) c = 1;
      cat[i] = c;

      // Targets: top points crystallize toward seeded real projection coords.
      if ((c === 3 || c === 4) && proj.length) {
        const p = proj[Math.floor(rand() * proj.length)];
        targets[i * 3] = p.x * 7;
        targets[i * 3 + 1] = p.y * 7;
        targets[i * 3 + 2] = 0;
      } else if (c === 2) {
        // traps fall down and out
        targets[i * 3] = px * 1.4;
        targets[i * 3 + 1] = py - 6;
        targets[i * 3 + 2] = pz;
      } else if (c === 1) {
        targets[i * 3] = px * 0.55;
        targets[i * 3 + 1] = py * 0.55;
        targets[i * 3 + 2] = pz * 0.55;
      } else {
        targets[i * 3] = px * 1.6;
        targets[i * 3 + 1] = py * 1.6;
        targets[i * 3 + 2] = pz * 1.6 - 4;
      }

      COL_POOL.toArray(colors, i * 3);
    }

    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    g.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    return {
      geometry: g,
      meta: { cat, targets, base: positions.slice() },
    };
  }, [funnel, count]);

  // Animate per-frame: lerp positions toward act-appropriate targets + recolor.
  useFrame((_, delta) => {
    const pts = ref.current;
    if (!pts) return;
    const posAttr = pts.geometry.getAttribute("position") as THREE.BufferAttribute;
    const colAttr = pts.geometry.getAttribute("color") as THREE.BufferAttribute;
    const pos = posAttr.array as Float32Array;
    const col = colAttr.array as Float32Array;
    const { cat, targets, base } = meta;
    const k = Math.min(1, delta * 2.2);

    for (let i = 0; i < cat.length; i++) {
      const c = cat[i];
      // Decide this point's current target + color based on act.
      let tx = base[i * 3],
        ty = base[i * 3 + 1],
        tz = base[i * 3 + 2];
      let color = COL_POOL;

      if (act >= 1) {
        // shortlist ignite
        if (c === 0) {
          color = COL_POOL;
        } else {
          color = COL_SHORT;
          tx = targets[i * 3] * 0.85 + base[i * 3] * 0.15;
          ty = targets[i * 3 + 1] * 0.85 + base[i * 3 + 1] * 0.15;
          tz = targets[i * 3 + 2] * 0.85 + base[i * 3 + 2] * 0.15;
        }
      }
      if (act >= 2 && c === 2) {
        color = COL_TRAP;
        tx = targets[i * 3];
        ty = targets[i * 3 + 1];
        tz = targets[i * 3 + 2];
      }
      if (act >= 3) {
        if (c === 3 || c === 4) {
          color = COL_TOP;
          tx = targets[i * 3];
          ty = targets[i * 3 + 1];
          tz = targets[i * 3 + 2];
        } else if (c === 1) {
          // shortlist non-top recede
          color = COL_SHORT;
          tx = base[i * 3] * 1.8;
          ty = base[i * 3 + 1] * 1.8;
          tz = base[i * 3 + 2] * 1.8 - 6;
        } else if (c === 0) {
          tx = base[i * 3] * 2.2;
          ty = base[i * 3 + 1] * 2.2;
          tz = base[i * 3 + 2] * 2.2 - 10;
        }
      }

      pos[i * 3] += (tx - pos[i * 3]) * k;
      pos[i * 3 + 1] += (ty - pos[i * 3 + 1]) * k;
      pos[i * 3 + 2] += (tz - pos[i * 3 + 2]) * k;

      col[i * 3] += (color.r - col[i * 3]) * k;
      col[i * 3 + 1] += (color.g - col[i * 3 + 1]) * k;
      col[i * 3 + 2] += (color.b - col[i * 3 + 2]) * k;
    }
    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
    pts.rotation.y += delta * 0.04;
  });

  return (
    <points ref={ref} geometry={geometry}>
      <pointsMaterial
        ref={matRef}
        size={0.06}
        sizeAttenuation
        vertexColors
        transparent
        opacity={0.9}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

export default function ParticleFunnel({ funnel, act, count }: Props) {
  return (
    <Canvas
      camera={{ position: [0, 0, 12], fov: 60 }}
      dpr={[1, 1.5]}
      gl={{ antialias: false, powerPreference: "high-performance" }}
      style={{ width: "100%", height: "100%" }}
    >
      <Points funnel={funnel} act={act} count={count} />
    </Canvas>
  );
}
