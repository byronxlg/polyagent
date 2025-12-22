import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { SimulationData } from '@/hooks/useSimulationData'
import { api, type Message } from '@/lib/api'
import { formatDateTimeShort } from '@/lib/utils'
import { Link } from '@tanstack/react-router'
import { Loader2, MessageSquare, Send, User } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

interface MessagesPageProps {
  simulationData: SimulationData
}

interface Conversation {
  principals: [string, string] // Principal IDs
  agentIds: [string, string] // Agent IDs for display
  messages: Message[]
  lastMessageAt: Date
  unreadCount: number
}

function getConversationKey(principalA: string, principalB: string): string {
  const sorted = [principalA, principalB].sort()
  return sorted.join('-')
}

export function MessagesPage({ simulationData }: MessagesPageProps) {
  const {
    messages: initialMessages,
    agents,
    principals,
    currentSimulation,
    getPrincipalName,
    loadData,
  } = simulationData
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const [selectedConversationKey, setSelectedConversationKey] = useState<
    string | null
  >(null)
  const [hasMore, setHasMore] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [total, setTotal] = useState<number | null>(null)
  const [messageContent, setMessageContent] = useState('')
  const [isSending, setIsSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Get first human principal to send from
  const currentUserPrincipal = principals.find(p => p.principal_type === 'human')

  // Helper to get agent from principal ID (returns undefined if principal is not an agent)
  const getAgentByPrincipalId = (principalId: string) => {
    return agents.find((a) => a.principal_id === principalId)
  }

  // Scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    setMessages(initialMessages)
    setHasMore(initialMessages.length >= 30)
  }, [initialMessages])

  const loadMore = async () => {
    setIsLoadingMore(true)
    try {
      const res = await api.messages.list(undefined, 30, messages.length)
      setMessages((prev) => [...prev, ...res.items])
      setHasMore(res.has_more)
      setTotal(res.total)
    } catch (error) {
      console.error('Failed to load more messages:', error)
    } finally {
      setIsLoadingMore(false)
    }
  }

  const handleSendMessage = async () => {
    if (!messageContent.trim() || !currentUserPrincipal || !selectedConversation) {
      return
    }

    // Determine recipient (the other principal in the conversation)
    const recipientPrincipalId = selectedConversation.principals.find(
      p => p !== currentUserPrincipal.id
    )
    if (!recipientPrincipalId) return

    setIsSending(true)
    try {
      await api.messages.send({
        from_principal_id: currentUserPrincipal.id,
        to_principal_id: recipientPrincipalId,
        content: messageContent.trim(),
      })
      setMessageContent('')
      // Reload messages to show the new one
      await loadData()
      // Scroll to bottom after sending
      setTimeout(() => scrollToBottom(), 100)
    } catch (error) {
      console.error('Failed to send message:', error)
      alert('Failed to send message. Please try again.')
    } finally {
      setIsSending(false)
    }
  }

  // Group messages into conversations (includes agent-to-agent, agent-to-human, and human-to-agent)
  const conversationsMap = new Map<string, Conversation>()

  for (const message of messages) {
    // Get agents for both principals (may be undefined for humans)
    const fromAgent = getAgentByPrincipalId(message.from_principal_id)
    const toAgent = getAgentByPrincipalId(message.to_principal_id)

    const key = getConversationKey(
      message.from_principal_id,
      message.to_principal_id
    )

    if (!conversationsMap.has(key)) {
      const sortedPrincipals = [
        message.from_principal_id,
        message.to_principal_id,
      ].sort()
      // Store agent IDs if available, otherwise use principal IDs for fallback
      const sortedAgents = [
        fromAgent?.id || message.from_principal_id,
        toAgent?.id || message.to_principal_id,
      ].sort()
      conversationsMap.set(key, {
        principals: [sortedPrincipals[0], sortedPrincipals[1]],
        agentIds: [sortedAgents[0], sortedAgents[1]],
        messages: [],
        lastMessageAt: new Date(message.sent_at),
        unreadCount: 0,
      })
    }

    const conversation = conversationsMap.get(key)!
    conversation.messages.push(message)

    const messageDate = new Date(message.sent_at)
    if (messageDate > conversation.lastMessageAt) {
      conversation.lastMessageAt = messageDate
    }

    if (!message.received_at) {
      conversation.unreadCount++
    }
  }

  // Sort conversations by last message time (newest first)
  const conversations = Array.from(conversationsMap.values()).sort(
    (a, b) => b.lastMessageAt.getTime() - a.lastMessageAt.getTime()
  )

  // Sort messages within each conversation by time (oldest first for reading order)
  for (const conversation of conversations) {
    conversation.messages.sort(
      (a, b) => new Date(a.sent_at).getTime() - new Date(b.sent_at).getTime()
    )
  }

  // Auto-select first conversation if none selected and conversations exist
  useEffect(() => {
    if (conversations.length > 0 && !selectedConversationKey) {
      const firstKey = getConversationKey(
        conversations[0].principals[0],
        conversations[0].principals[1]
      )
      setSelectedConversationKey(firstKey)
    }
  }, [conversations, selectedConversationKey])

  // Scroll to bottom when conversation changes
  useEffect(() => {
    if (selectedConversationKey) {
      setTimeout(() => {
        scrollToBottom()
      }, 100)
    }
  }, [selectedConversationKey])

  const selectedConversation = conversations.find((c) => {
    const key = getConversationKey(c.principals[0], c.principals[1])
    return key === selectedConversationKey
  })

  return (
    <div className="px-6 pt-6 pb-2">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Conversations</h1>
        <span className="text-sm text-muted-foreground">
          {conversations.length} conversations, {messages.length}
          {total !== null ? ` of ${total}` : ''} messages
        </span>
      </div>

      <div className="flex gap-4 h-[calc(100vh-9rem)]">
        {/* Left Sidebar - Conversation List */}
        <div className="w-80 flex flex-col border rounded-lg">
          <div className="flex-1 overflow-y-auto p-2">
            <div className="space-y-1">
              {conversations.map((conversation) => {
                const key = getConversationKey(
                  conversation.principals[0],
                  conversation.principals[1]
                )
                const isSelected = key === selectedConversationKey
                const lastMessage =
                  conversation.messages[conversation.messages.length - 1]

                return (
                  <div
                    key={key}
                    onClick={() => setSelectedConversationKey(key)}
                    className={`p-3 rounded-lg cursor-pointer transition-colors ${
                      isSelected ? 'bg-muted' : 'hover:bg-muted/50'
                    }`}
                  >
                    <div className="flex items-center gap-1.5 mb-2 min-w-0">
                      <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-zinc-700 text-white text-xs font-bold flex-shrink-0">
                        <User className="h-2.5 w-2.5" />
                      </span>
                      <span className="text-xs font-medium truncate min-w-0 flex-1">
                        {getPrincipalName(conversation.principals[0])}
                      </span>
                      <MessageSquare className="h-2.5 w-2.5 text-muted-foreground flex-shrink-0" />
                      <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-zinc-700 text-white text-xs font-bold flex-shrink-0">
                        <User className="h-2.5 w-2.5" />
                      </span>
                      <span className="text-xs font-medium truncate min-w-0 flex-1">
                        {getPrincipalName(conversation.principals[1])}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate mb-2">
                      {lastMessage.content.length > 40
                        ? `${lastMessage.content.slice(0, 40)}...`
                        : lastMessage.content}
                    </p>
                    <div className="flex items-center gap-1.5">
                      <Badge
                        variant="secondary"
                        className="text-[10px] px-1.5 py-0 h-4 flex-shrink-0"
                      >
                        {conversation.messages.length}
                      </Badge>
                      {conversation.unreadCount > 0 && (
                        <Badge className="bg-blue-500 text-[10px] px-1.5 py-0 h-4 flex-shrink-0">
                          {conversation.unreadCount}
                        </Badge>
                      )}
                      <span className="text-[10px] text-muted-foreground ml-auto flex-shrink-0">
                        {formatDateTimeShort(
                          conversation.lastMessageAt.toISOString()
                        )}
                      </span>
                    </div>
                  </div>
                )
              })}
              {conversations.length === 0 && (
                <div className="text-center text-muted-foreground py-8 text-sm">
                  No conversations found
                </div>
              )}
            </div>
          </div>
          {hasMore && messages.length > 0 && (
            <div className="border-t p-2">
              <Button
                variant="outline"
                size="sm"
                onClick={loadMore}
                disabled={isLoadingMore}
                className="w-full"
              >
                {isLoadingMore ? (
                  <>
                    <Loader2 className="h-3 w-3 animate-spin mr-2" />
                    Loading...
                  </>
                ) : (
                  'Load More'
                )}
              </Button>
            </div>
          )}
        </div>

        {/* Right Main Pane - Messages */}
        <div className="flex-1 flex flex-col border rounded-lg">
          {selectedConversation ? (
            <>
              {/* Conversation Header */}
              <div className="border-b p-4 bg-muted/20">
                <div className="flex items-center gap-3">
                  {getAgentByPrincipalId(selectedConversation.principals[0]) ? (
                    <Link
                      to="/simulations/$simulationId/agents/$id"
                      params={{
                        simulationId: String(currentSimulation?.id),
                        id: String(selectedConversation.agentIds[0]),
                      }}
                      className="inline-flex items-center gap-2 hover:underline"
                    >
                      <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-zinc-700 text-white text-sm font-bold hover:bg-zinc-600">
                        <User className="h-4 w-4" />
                      </span>
                      <span className="font-medium">
                        {getPrincipalName(selectedConversation.principals[0])}
                      </span>
                    </Link>
                  ) : (
                    <div className="inline-flex items-center gap-2">
                      <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-zinc-700 text-white text-sm font-bold">
                        <User className="h-4 w-4" />
                      </span>
                      <span className="font-medium">
                        {getPrincipalName(selectedConversation.principals[0])}
                      </span>
                    </div>
                  )}
                  <MessageSquare className="h-4 w-4 text-muted-foreground" />
                  {getAgentByPrincipalId(selectedConversation.principals[1]) ? (
                    <Link
                      to="/simulations/$simulationId/agents/$id"
                      params={{
                        simulationId: String(currentSimulation?.id),
                        id: String(selectedConversation.agentIds[1]),
                      }}
                      className="inline-flex items-center gap-2 hover:underline"
                    >
                      <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-zinc-700 text-white text-sm font-bold hover:bg-zinc-600">
                        <User className="h-4 w-4" />
                      </span>
                      <span className="font-medium">
                        {getPrincipalName(selectedConversation.principals[1])}
                      </span>
                    </Link>
                  ) : (
                    <div className="inline-flex items-center gap-2">
                      <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-zinc-700 text-white text-sm font-bold">
                        <User className="h-4 w-4" />
                      </span>
                      <span className="font-medium">
                        {getPrincipalName(selectedConversation.principals[1])}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4">
                <div className="space-y-4">
                  {selectedConversation.messages.map((message) => {
                    const fromAgent = getAgentByPrincipalId(
                      message.from_principal_id
                    )
                    const isFirstPrincipal =
                      message.from_principal_id ===
                      selectedConversation.principals[0]

                    return (
                      <div
                        key={message.id}
                        className={`flex gap-3 ${
                          isFirstPrincipal ? '' : 'flex-row-reverse'
                        }`}
                      >
                        {fromAgent ? (
                          <Link
                            to="/simulations/$simulationId/agents/$id"
                            params={{
                              simulationId: String(currentSimulation?.id),
                              id: String(fromAgent.id),
                            }}
                            className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-zinc-700 text-white text-sm font-bold hover:bg-zinc-600 shrink-0"
                          >
                            <User className="h-4 w-4" />
                          </Link>
                        ) : (
                          <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-zinc-700 text-white text-sm font-bold shrink-0">
                            <User className="h-4 w-4" />
                          </span>
                        )}
                        <div
                          className={`flex-1 max-w-[70%] ${
                            isFirstPrincipal ? '' : 'text-right'
                          }`}
                        >
                          <div
                            className={`text-xs font-medium mb-1 ${
                              isFirstPrincipal ? '' : 'text-right'
                            }`}
                          >
                            {getPrincipalName(message.from_principal_id)}
                          </div>
                          <div
                            className={`inline-block p-3 rounded-lg text-sm ${
                              isFirstPrincipal
                                ? 'bg-muted rounded-tl-none'
                                : 'bg-primary/20 rounded-tr-none'
                            }`}
                          >
                            {message.content}
                          </div>
                          <div
                            className={`flex items-center gap-2 mt-1 ${
                              isFirstPrincipal ? '' : 'justify-end'
                            }`}
                          >
                            <span className="text-[10px] text-muted-foreground">
                              {formatDateTimeShort(message.sent_at)}
                            </span>
                            {!message.received_at && (
                              <Badge className="bg-blue-500 text-[10px] px-1 py-0 h-4">
                                Unread
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                  <div ref={messagesEndRef} />
                </div>
              </div>

              {/* Message Input */}
              {currentUserPrincipal && (
                <div className="border-t p-4 bg-muted/20">
                  <div className="flex gap-2">
                    <Textarea
                      value={messageContent}
                      onChange={(e) => setMessageContent(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          handleSendMessage()
                        }
                      }}
                      placeholder="Type your message... (Press Enter to send, Shift+Enter for new line)"
                      className="min-h-[60px] resize-none"
                      disabled={isSending}
                    />
                    <Button
                      onClick={handleSendMessage}
                      disabled={!messageContent.trim() || isSending}
                      size="icon"
                      className="h-[60px] w-[60px] shrink-0"
                    >
                      {isSending ? (
                        <Loader2 className="h-5 w-5 animate-spin" />
                      ) : (
                        <Send className="h-5 w-5" />
                      )}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Sending as {currentUserPrincipal.username}
                  </p>
                </div>
              )}
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <MessageSquare className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p className="text-sm">
                  Select a conversation to view messages
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
