import { useEffect } from "react";
import { motion, useSpring, useTransform } from "framer-motion";

export default function AnimatedNumber({ value, prefix = "", suffix = "", formatter = null }) {
  const spring = useSpring(0, { mass: 0.8, stiffness: 75, damping: 15 });
  const display = useTransform(spring, (current) => {
    const rounded = Math.round(current);
    if (formatter) return `${prefix}${formatter(rounded)}${suffix}`;
    return `${prefix}${rounded.toLocaleString()}${suffix}`;
  });

  useEffect(() => {
    spring.set(value);
  }, [spring, value]);

  return <motion.span>{display}</motion.span>;
}
