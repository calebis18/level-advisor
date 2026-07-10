import { useEffect, useState } from 'react';
import { api } from './api';

const departments = ['Computer Science', 'Software Engineering', 'Information Technology', 'Mathematics', 'Other'];
const levels = ['100 Level', '200 Level', '300 Level', '400 Level', '500 Level'];
const emptyRegistration = { firstName: '', lastName: '', matricNumber: '', email: '', department: '', level: '', password: '', confirmPassword: '' };

function Field({ label, error, ...props }) {
  return <label className="field"><span>{label}</span><input {...props} />{error && <small>{error}</small>}</label>;
}

function AuthPage({ mode, onSuccess, changeMode }) {
  const [form, setForm] = useState(mode === 'register' ? emptyRegistration : { identifier: '', password: '' });
  const [errors, setErrors] = useState({});
  const [message, setMessage] = useState('');
  const update = (event) => setForm({ ...form, [event.target.name]: event.target.value });
  const submit = async (event) => {
    event.preventDefault(); setErrors({}); setMessage('');
    try {
      const result = await api(mode === 'register' ? '/api/register' : '/api/login', { method: 'POST', body: JSON.stringify(form) });
      onSuccess(result.user);
    } catch (error) {
      setMessage(error.error || 'Something went wrong.'); setErrors(error.fields || {});
    }
  };
  const registration = mode === 'register';
  return <main className="auth-shell"><section className="auth-card">
    <p className="eyebrow">LEVEL ADVISOR</p><h1>{registration ? 'Create your student account' : 'Welcome back'}</h1>
    <p className="subtext">{registration ? 'Set up your profile to receive advice that fits your academic journey.' : 'Log in to continue your conversation.'}</p>
    {message && <div className="form-message">{message}</div>}
    <form onSubmit={submit} noValidate>
      {registration && <div className="two-columns"><Field label="First name" name="firstName" value={form.firstName} onChange={update} error={errors.firstName} /><Field label="Last name" name="lastName" value={form.lastName} onChange={update} error={errors.lastName} /></div>}
      {registration ? <><Field label="Matric number" name="matricNumber" placeholder="e.g. CSC/2024/001" value={form.matricNumber} onChange={update} error={errors.matricNumber} /><Field label="University email" type="email" name="email" placeholder="you@university.edu" value={form.email} onChange={update} error={errors.email} />
        <div className="two-columns"><label className="field"><span>Department</span><select name="department" value={form.department} onChange={update}><option value="">Select department</option>{departments.map((item) => <option key={item}>{item}</option>)}</select>{errors.department && <small>{errors.department}</small>}</label><label className="field"><span>Current level</span><select name="level" value={form.level} onChange={update}><option value="">Select level</option>{levels.map((item) => <option key={item}>{item}</option>)}</select>{errors.level && <small>{errors.level}</small>}</label></div></> : <Field label="Email or matric number" name="identifier" value={form.identifier} onChange={update} error={errors.identifier} />}
      <Field label="Password" type="password" name="password" value={form.password} onChange={update} error={errors.password} />
      {registration && <Field label="Confirm password" type="password" name="confirmPassword" value={form.confirmPassword} onChange={update} error={errors.confirmPassword} />}
      <button className="primary" type="submit">{registration ? 'Create account' : 'Log in'}</button>
    </form>
    <p className="switch">{registration ? 'Already registered?' : 'New here?'} <button onClick={() => changeMode(registration ? 'login' : 'register')}>{registration ? 'Log in' : 'Create an account'}</button></p>
  </section></main>;
}

function ChatPage({ user, onLogout }) {
  const [messages, setMessages] = useState([{ role: 'advisor', content: `Hi ${user.firstName}! I can help with courses, exams, registration, and university life.` }]);
  const [text, setText] = useState(''); const [sending, setSending] = useState(false);
  const send = async (event) => { event.preventDefault(); const message = text.trim(); if (!message || sending) return; setText(''); setSending(true); setMessages((items) => [...items, { role: 'student', content: message }]); try { const result = await api('/api/chat', { method: 'POST', body: JSON.stringify({ message }) }); setMessages((items) => [...items, { role: 'advisor', content: result.reply, ai: result.aiPowered }]); } catch (error) { setMessages((items) => [...items, { role: 'advisor', content: error.error || 'I could not send that message. Please try again.' }]); } finally { setSending(false); } };
  return <main className="chat-shell"><aside className="profile"><p className="eyebrow">LEVEL ADVISOR</p><h2>{user.firstName} {user.lastName}</h2><p>{user.matricNumber}</p><div className="profile-detail"><span>Department</span>{user.department}</div><div className="profile-detail"><span>Level</span>{user.level}</div><button className="secondary" onClick={onLogout}>Log out</button></aside><section className="conversation"><header><div><p className="eyebrow">YOUR ACADEMIC COMPANION</p><h1>How can I help today?</h1></div><div className="header-actions"><span className="online">● Online</span><button className="logout-icon" onClick={onLogout} aria-label="Log out" title="Log out">⇥</button></div></header><div className="messages">{messages.map((message, index) => <article className={`message ${message.role}`} key={index}><strong>{message.role === 'student' ? 'You' : 'Level Advisor'} {message.ai && <em>AI</em>}</strong><p>{message.content}</p></article>)}</div><form className="composer" onSubmit={send}><textarea value={text} onChange={(event) => setText(event.target.value)} placeholder="Ask about courses, exams, or registration..." rows="2" maxLength="2000" /><button className="primary" disabled={sending}>{sending ? 'Sending…' : 'Send'}</button></form></section></main>;
}

export default function App() {
  const [user, setUser] = useState(null); const [mode, setMode] = useState('register'); const [loading, setLoading] = useState(true);
  // A visit to the portal always begins at login; do not restore an old chat session.
  useEffect(() => { api('/api/logout', { method: 'POST' }).catch(() => {}).finally(() => setLoading(false)); }, []);
  const logout = async () => { await api('/api/logout', { method: 'POST' }); setUser(null); setMode('login'); };
  if (loading) return <main className="auth-shell">Loading your portal…</main>;
  return user ? <ChatPage user={user} onLogout={logout} /> : <AuthPage mode={mode} onSuccess={setUser} changeMode={setMode} />;
}
