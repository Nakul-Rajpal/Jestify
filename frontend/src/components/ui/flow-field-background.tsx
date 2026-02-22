"use client";

import React, { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

interface NeuralBackgroundProps {
  className?: string;
  /**
   * Color of the particles.
   * Defaults to a cyan/indigo mix if not specified.
   */
  color?: string;
  /**
   * The opacity of the trails (0.0 to 1.0).
   * Lower = longer trails. Higher = shorter trails.
   * Default: 0.1
   */
  trailOpacity?: number;
  /**
   * Number of particles. Default: 800
   */
  particleCount?: number;
  /**
   * Speed multiplier. Default: 1
   */
  speed?: number;
  /**
   * Mouse interaction behavior.
   * - "attract": particles follow the cursor
   * - "repel": particles move away from the cursor
   * Default: "attract"
   */
  mouseMode?: "attract" | "repel";
  /**
   * Strength of mouse interaction force.
   * Default: 0.05
   */
  mouseStrength?: number;
  /**
   * Radius in px where mouse affects particles.
   * Default: 180
   */
  interactionRadius?: number;
}

export default function NeuralBackground({
  className,
  color = "#6366f1",
  trailOpacity = 0.15,
  particleCount = 600,
  speed = 1,
  mouseMode = "attract",
  mouseStrength = 0.05,
  interactionRadius = 180,
}: NeuralBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    type Particle = {
      x: number;
      y: number;
      vx: number;
      vy: number;
      age: number;
      life: number;
    };

    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = container.clientWidth;
    let height = container.clientHeight;
    let particles: Particle[] = [];
    let animationFrameId: number;
    const mouse = { x: -1000, y: -1000 };

    const createParticle = (): Particle => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: 0,
      vy: 0,
      age: 0,
      life: Math.random() * 200 + 100,
    });

    const resetParticle = (particle: Particle) => {
      particle.x = Math.random() * width;
      particle.y = Math.random() * height;
      particle.vx = 0;
      particle.vy = 0;
      particle.age = 0;
      particle.life = Math.random() * 200 + 100;
    };

    const updateParticle = (particle: Particle) => {
      const angle =
        (Math.cos(particle.x * 0.005) + Math.sin(particle.y * 0.005)) * Math.PI;

      particle.vx += Math.cos(angle) * 0.2 * speed;
      particle.vy += Math.sin(angle) * 0.2 * speed;

      const dx = mouse.x - particle.x;
      const dy = mouse.y - particle.y;
      const distance = Math.sqrt(dx * dx + dy * dy);

      if (distance < interactionRadius) {
        const force = (interactionRadius - distance) / interactionRadius;
        const direction = mouseMode === "repel" ? -1 : 1;
        particle.vx += dx * force * mouseStrength * direction;
        particle.vy += dy * force * mouseStrength * direction;
      }

      particle.x += particle.vx;
      particle.y += particle.vy;
      particle.vx *= 0.95;
      particle.vy *= 0.95;

      particle.age++;
      if (particle.age > particle.life) {
        resetParticle(particle);
      }

      if (particle.x < 0) particle.x = width;
      if (particle.x > width) particle.x = 0;
      if (particle.y < 0) particle.y = height;
      if (particle.y > height) particle.y = 0;
    };

    const drawParticle = (particle: Particle, context: CanvasRenderingContext2D) => {
      context.fillStyle = color;
      const alpha = 1 - Math.abs(particle.age / particle.life - 0.5) * 2;
      context.globalAlpha = alpha;
      context.fillRect(particle.x, particle.y, 1.5, 1.5);
    };

    const init = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;

      particles = [];
      for (let i = 0; i < particleCount; i++) {
        particles.push(createParticle());
      }
    };

    const animate = () => {
      ctx.globalAlpha = 1;
      ctx.fillStyle = `rgba(0, 0, 0, ${trailOpacity})`;
      ctx.fillRect(0, 0, width, height);

      particles.forEach((p) => {
        updateParticle(p);
        drawParticle(p, ctx);
      });

      animationFrameId = requestAnimationFrame(animate);
    };

    const handleResize = () => {
      width = container.clientWidth;
      height = container.clientHeight;
      init();
    };

    const handleMouseMove = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      if (x >= 0 && x <= rect.width && y >= 0 && y <= rect.height) {
        mouse.x = x;
        mouse.y = y;
      } else {
        mouse.x = -1000;
        mouse.y = -1000;
      }
    };

    const handleMouseLeave = () => {
      mouse.x = -1000;
      mouse.y = -1000;
    };

    init();
    animate();

    window.addEventListener("resize", handleResize);
    // Track pointer globally so interaction still works when the background
    // layer itself has pointer-events disabled.
    window.addEventListener("pointermove", handleMouseMove);
    window.addEventListener("blur", handleMouseLeave);

    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("pointermove", handleMouseMove);
      window.removeEventListener("blur", handleMouseLeave);
      cancelAnimationFrame(animationFrameId);
    };
  }, [
    color,
    interactionRadius,
    mouseMode,
    mouseStrength,
    particleCount,
    speed,
    trailOpacity,
  ]);

  return (
    <div
      ref={containerRef}
      className={cn("relative h-full w-full overflow-hidden bg-black", className)}
    >
      <canvas ref={canvasRef} className="block h-full w-full" />
    </div>
  );
}
