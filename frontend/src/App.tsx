import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { fetchAgents, sendChat } from "./api";
import type { AgentName, ChatResponse, SaveBucket } from "./types";

const defaultAgent: AgentName = "yapper";

export default function App() {
  const [agents, setAgents] = useState<string[]>([]);
  const [activeAgent, setActiveAgent] = useState<AgentName>(defaultAgent);
  const [message, setMessage] = useState("");
  const [saveTo, setSaveTo] = useState<SaveBucket | "">("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ChatResponse | null>(null);

  useEffect(() => {
    fetchAgents()
      .then(setAgents)
      .catch((err: Error) => setError(err.message));
  }, []);

  async function onSubmit() {
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await sendChat({
        message,
        active_agent: activeAgent,
        enabled_agents: [activeAgent],
        model_name: "gpt-4o-mini",
        save_to: saveTo || undefined,
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box sx={{ maxWidth: 900, mx: "auto", py: 6, px: 2 }}>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        CSE443 Multi-Agent Test UI
      </Typography>

      <Card>
        <CardContent>
          <Stack spacing={2}>
            <FormControl fullWidth>
              <InputLabel id="agent-label">Agent</InputLabel>
              <Select
                labelId="agent-label"
                value={activeAgent}
                label="Agent"
                onChange={(e) => setActiveAgent(e.target.value as AgentName)}
              >
                {(agents.length ? agents : [defaultAgent]).map((a) => (
                  <MenuItem key={a} value={a}>
                    {a}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl fullWidth>
              <InputLabel id="save-label">Save To (optional)</InputLabel>
              <Select
                labelId="save-label"
                value={saveTo}
                label="Save To (optional)"
                onChange={(e) => setSaveTo(e.target.value as SaveBucket | "")}
              >
                <MenuItem value="">No save</MenuItem>
                <MenuItem value="journal">journal</MenuItem>
                <MenuItem value="definitions">definitions</MenuItem>
                <MenuItem value="threads">threads</MenuItem>
                <MenuItem value="drafts">drafts</MenuItem>
                <MenuItem value="audit_logs">audit_logs</MenuItem>
              </Select>
            </FormControl>

            <TextField
              label="Message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              multiline
              minRows={4}
              placeholder="Describe symptoms, ask for definitions, or request related Reddit threads."
            />

            <Button variant="contained" disabled={!message.trim() || loading} onClick={onSubmit}>
              {loading ? <CircularProgress size={20} color="inherit" /> : "Send"}
            </Button>
          </Stack>
        </CardContent>
      </Card>

      {error && (
        <Alert severity="error" sx={{ mt: 3 }}>
          {error}
        </Alert>
      )}

      {result && (
        <Card sx={{ mt: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Response ({result.active_agent})
            </Typography>
            <Typography whiteSpace="pre-wrap">{result.response}</Typography>

            {result.tool_results.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle1" fontWeight={700}>
                  Local Thread Matches
                </Typography>
                {result.tool_results.map((r) => (
                  <Box key={`${r.url}-${r.score}`} sx={{ mt: 1 }}>
                    <Typography fontWeight={600}>{r.title}</Typography>
                    <Typography variant="body2">{r.url}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      score={r.score} ups={r.ups} comments={r.comments}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
