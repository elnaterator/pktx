// The SPA is served same-origin as the `/mcp` endpoint, so derive the URL from
// the current page origin at runtime — correct for localhost, dev, and prod
// without a per-environment rebuild. `VITE_MCP_SERVER_URL` stays an explicit
// override for `vite dev`, where the SPA (:5173) and backend (:8000) differ.
export function getMcpUrl(): string {
  return (
    import.meta.env.VITE_MCP_SERVER_URL ??
    (typeof window !== 'undefined'
      ? `${window.location.origin}/mcp`
      : 'https://your-pktx-server.com/mcp')
  )
}
