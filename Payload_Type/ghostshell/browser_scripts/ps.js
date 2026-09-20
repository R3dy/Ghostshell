/*
 * ghostshell `ps` browser script -- renders process listings in the Mythic UI.
 *
 * The agent returns the Mythic process-browser structure
 * ({"processes": {"host":..., "os":..., "processes": [...]}}), which the
 * Mythic server consumes for the unified per-host Process Browser. This
 * script additionally renders the task's own output as a sortable table so
 * the operator sees the listing inline in the task view too.
 */
function(task, responses) {
  if (task.status.toLowerCase().includes("error")) {
    return { "plaintext": responses.join("") };
  }

  const rows = [];
  for (let i = 0; i < responses.length; i++) {
    try {
      const parsed = JSON.parse(responses[i]);
      const listing = parsed && parsed.processes && Array.isArray(parsed.processes.processes)
        ? parsed.processes.processes
        : (Array.isArray(parsed) ? parsed : []);
      for (let j = 0; j < listing.length; j++) {
        rows.push(listing[j]);
      }
    } catch (error) {
      // Responses can arrive incrementally / partially completed -- ignore
      // chunks that aren't a full JSON process listing yet.
    }
  }

  if (rows.length === 0) {
    return { "plaintext": responses.join("") || "No processes returned." };
  }

  return {
    "table": [{
      "title": "Processes",
      "headers": [
        { "plaintext": "pid", "type": "number", "width": 90 },
        { "plaintext": "ppid", "type": "number", "width": 90 },
        { "plaintext": "user", "type": "string", "width": 160 },
        { "plaintext": "name", "type": "string", "width": 200 },
        { "plaintext": "command_line", "type": "string", "fillWidth": true }
      ],
      "rows": rows.map((p) => ({
        "pid": { "plaintext": String(p.process_id) },
        "ppid": { "plaintext": String(p.parent_process_id) },
        "user": { "plaintext": p.user || "" },
        "name": { "plaintext": p.name || "" },
        "command_line": { "plaintext": p.command_line || p.bin_path || "" }
      }))
    }]
  };
}
