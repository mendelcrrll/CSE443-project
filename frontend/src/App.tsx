import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  alpha,
  styled,
  useTheme,
} from "@mui/material/styles";
import {
  Alert,
  AppBar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  FormControl,
  IconButton,
  InputLabel,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Toolbar,
  Typography,
  useMediaQuery,
} from "@mui/material";
import MenuOpenIcon from "@mui/icons-material/MenuOpen";
import { fetchAgents, sendChat } from "./api";
import type { AgentName, SaveBucket, SearchResult } from "./types";

const defaultAgent: AgentName = "yapper";
const SIDEBAR_WIDTH = 300;
const APPBAR_HEIGHT = 72;

const StyledToolbar = styled(Toolbar)(({ theme }) => ({
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  flexShrink: 0,
  borderRadius: `calc(${theme.shape.borderRadius}px + 8px)`,
  backdropFilter: "blur(18px)",
  border: "1px solid",
  borderColor: theme.palette.divider,
  backgroundColor: alpha(theme.palette.background.paper, 0.7),
  boxShadow: theme.shadows[1],
  padding: "8px 12px",
}));

type MessageItem = {
  id: string;
  role: "user" | "assistant";
  agent: AgentName;
  text: string;
  toolResults?: SearchResult[];
};

const bucketOptions: Array<SaveBucket | ""> = [
  "",
  "journal",
  "definitions",
  "threads",
  "drafts",
  "audit_logs",
];

export default function App() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));
  const [sidebarOpen, setSidebarOpen] = useState(!isMobile);
  const [agents, setAgents] = useState<string[]>([]);
  const [activeAgent, setActiveAgent] = useState<AgentName>(defaultAgent);
  const [modelName, setModelName] = useState("gpt-4o-mini");
  const [message, setMessage] = useState("");
  const [saveTo, setSaveTo] = useState<SaveBucket | "">("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [messages, setMessages] = useState<MessageItem[]>([]);

  const availableAgents = useMemo(
    () => (agents.length ? agents : [defaultAgent]),
    [agents]
  );

  useEffect(() => {
    fetchAgents()
      .then(setAgents)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    setSidebarOpen(!isMobile);
  }, [isMobile]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!message.trim()) return;

    const userMessage = message.trim();
    const userItem: MessageItem = {
      id: crypto.randomUUID(),
      role: "user",
      agent: activeAgent,
      text: userMessage,
    };

    setMessages((prev) => [...prev, userItem]);
    setMessage("");
    setLoading(true);
    setError("");

    try {
      const response = await sendChat({
        message: userMessage,
        active_agent: activeAgent,
        enabled_agents: [activeAgent],
        model_name: modelName,
        save_to: saveTo || undefined,
      });

      const assistantItem: MessageItem = {
        id: crypto.randomUUID(),
        role: "assistant",
        agent: response.active_agent,
        text: response.response,
        toolResults: response.tool_results,
      };
      setMessages((prev) => [...prev, assistantItem]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box display="flex" sx={{ minHeight: "100vh" }}>
      <AppBar
        position="fixed"
        enableColorOnDark
        sx={{
          boxShadow: 0,
          bgcolor: "transparent",
          backgroundImage: "none",
          top: 0,
          left: sidebarOpen ? SIDEBAR_WIDTH : 0,
          width: sidebarOpen ? `calc(100% - ${SIDEBAR_WIDTH}px)` : "100%",
          transition: "all 0.25s ease",
          zIndex: (theme) => theme.zIndex.drawer + 1,
        }}
      >
        <Container maxWidth="xl">
          <StyledToolbar variant="dense" disableGutters>
            <Box display="flex" alignItems="center" gap={2}>
              <IconButton
                onClick={() => setSidebarOpen((o) => !o)}
                aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
              >
                <MenuOpenIcon
                  sx={{
                    transform: sidebarOpen ? "rotate(0deg)" : "rotate(180deg)",
                    transition: "transform 0.2s ease",
                  }}
                />
              </IconButton>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Multi-Agent Research Assistant
                </Typography>
                <Typography variant="body2" fontWeight={700}>
                  Messaging Workspace
                </Typography>
              </Box>
            </Box>
            <Chip size="small" label={`Active: ${activeAgent}`} color="primary" />
          </StyledToolbar>
        </Container>
      </AppBar>

      {sidebarOpen && (
        <Box
          sx={{
            width: SIDEBAR_WIDTH,
            flexShrink: 0,
            p: 2,
            overflowY: "auto",
            height: "100vh",
            borderRight: "1px solid",
            borderColor: "divider",
            bgcolor: "background.paper",
          }}
        >
          <Toolbar sx={{ minHeight: APPBAR_HEIGHT }} />
          <Stack spacing={2}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Agents
                </Typography>
                <List disablePadding>
                  {availableAgents.map((agent) => (
                    <ListItemButton
                      key={agent}
                      selected={activeAgent === agent}
                      onClick={() => setActiveAgent(agent as AgentName)}
                    >
                      <ListItemText
                        primary={agent}
                        secondary={activeAgent === agent ? "Current" : undefined}
                      />
                    </ListItemButton>
                  ))}
                </List>
              </CardContent>
            </Card>

            <Card variant="outlined">
              <CardContent>
                <Stack spacing={2}>
                  <TextField
                    label="Model"
                    value={modelName}
                    onChange={(e) => setModelName(e.target.value)}
                    size="small"
                  />
                  <FormControl fullWidth size="small">
                    <InputLabel id="save-label">Save bucket</InputLabel>
                    <Select
                      labelId="save-label"
                      value={saveTo}
                      label="Save bucket"
                      onChange={(e) => setSaveTo(e.target.value as SaveBucket | "")}
                    >
                      {bucketOptions.map((bucket) => (
                        <MenuItem key={bucket || "none"} value={bucket}>
                          {bucket || "No save"}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Stack>
              </CardContent>
            </Card>
          </Stack>
        </Box>
      )}

      <Box component="main" sx={{ flexGrow: 1, p: 2 }}>
        <Toolbar sx={{ minHeight: APPBAR_HEIGHT }} />
        <Paper
          elevation={0}
          sx={{
            height: "calc(100vh - 112px)",
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 3,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            bgcolor: "background.paper",
          }}
        >
          <Box sx={{ p: 2, borderBottom: "1px solid", borderColor: "divider" }}>
            <Typography variant="h6">Conversation</Typography>
            <Typography variant="body2" color="text.secondary">
              Chat with one agent at a time, keep context, and inspect tool results inline.
            </Typography>
          </Box>

          <Box sx={{ flexGrow: 1, overflowY: "auto", p: 2 }}>
            <Stack spacing={2}>
              {messages.length === 0 && (
                <Typography color="text.secondary">
                  Start by sending a message.
                </Typography>
              )}
              {messages.map((item) => (
                <Box
                  key={item.id}
                  sx={{
                    alignSelf: item.role === "user" ? "flex-end" : "flex-start",
                    maxWidth: "78%",
                  }}
                >
                  <Paper
                    sx={{
                      p: 1.5,
                      bgcolor: item.role === "user" ? "primary.main" : "grey.100",
                      color: item.role === "user" ? "primary.contrastText" : "text.primary",
                    }}
                  >
                    <Typography variant="caption" sx={{ opacity: 0.85 }}>
                      {item.role} via {item.agent}
                    </Typography>
                    <Typography whiteSpace="pre-wrap">{item.text}</Typography>
                  </Paper>

                  {item.toolResults && item.toolResults.length > 0 && (
                    <Card variant="outlined" sx={{ mt: 1 }}>
                      <CardContent sx={{ py: 1.5 }}>
                        <Typography variant="subtitle2" sx={{ mb: 1 }}>
                          Local Thread Matches
                        </Typography>
                        {item.toolResults.map((r) => (
                          <Box key={`${r.url}-${r.score}`} sx={{ mb: 1 }}>
                            <Typography fontWeight={600}>{r.title}</Typography>
                            <Typography variant="body2">{r.url}</Typography>
                            <Typography variant="caption" color="text.secondary">
                              score={r.score} ups={r.ups} comments={r.comments}
                            </Typography>
                          </Box>
                        ))}
                      </CardContent>
                    </Card>
                  )}
                </Box>
              ))}
            </Stack>
          </Box>

          <Box
            component="form"
            onSubmit={onSubmit}
            sx={{ p: 2, borderTop: "1px solid", borderColor: "divider" }}
          >
            <Stack direction="row" spacing={1}>
              <TextField
                fullWidth
                label="Message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                multiline
                maxRows={4}
                placeholder="Describe symptoms, ask for definitions, or request related community threads."
              />
              <Button
                type="submit"
                variant="contained"
                disabled={!message.trim() || loading}
                sx={{ minWidth: 110 }}
              >
                {loading ? <CircularProgress size={20} color="inherit" /> : "Send"}
              </Button>
            </Stack>
          </Box>
        </Paper>

        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </Box>
    </Box>
  );
}
