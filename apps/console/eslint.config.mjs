import next from "eslint-config-next";

const config = [
  ...next,
  { ignores: [".next/", "node_modules/", "src/lib/api-types.ts", "next-env.d.ts"] },
];

export default config;
