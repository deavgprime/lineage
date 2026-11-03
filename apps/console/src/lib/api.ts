import "server-only";

import createClient from "openapi-fetch";

import type { paths } from "./api-types";
import { accessToken } from "./auth";
import { serviceHeaders } from "./service-identity";

// The typed API client, generated from the API's OpenAPI schema. Used only on the server.
export async function api(returnTo = "/") {
  const token = await accessToken(returnTo);
  return createClient<paths>({
    baseUrl: process.env.LINEAGE_API_URL ?? "http://127.0.0.1:8000",
    headers: {
      Authorization: `Bearer ${token}`,
      ...(await serviceHeaders(process.env.LINEAGE_API_AUDIENCE)),
    },
    cache: "no-store",
  });
}
