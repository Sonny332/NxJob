const API_BASE_URL = "http://127.0.0.1:8765";

export type HealthResponse = {
  status: "ok";
  service: "nxjob-local-service";
  version: string;
};

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);

  if (!response.ok) {
    throw new Error(`NxJob local service returned ${response.status}.`);
  }

  return response.json() as Promise<HealthResponse>;
}

