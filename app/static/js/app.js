/**
 * ClinicPulse AI - Single Page Application Core
 * Interactive Dark Theme Client Logic
 */

const API_BASE = '/api';

const state = {
  token: localStorage.getItem('cp_token') || null,
  user: JSON.parse(localStorage.getItem('cp_user') || 'null'),
  currentTab: 'doctors',
  specialisations: [],
  selectedSpecialisation: 'All',
  searchQuery: '',
  doctors: [],
  appointments: [],
  notifications: [],
  
  // Booking Workflow State
  booking: {
    doctor: null,
    date: new Date().toISOString().split('T')[0],
    slots: [],
    selectedSlot: null,
    heldAppointmentId: null,
    holdExpiresAt: null,
    holdTimerInterval: null,
    aiPreSummary: null
  },

  // Doctor Consultation Workflow State
  consultation: {
    appointment: null,
    prescriptions: []
  },

  // Admin Dashboard State
  adminMetrics: null
};

// Initialize Application
document.addEventListener('DOMContentLoaded', async () => {
  initUIEventListeners();
  if (state.token && state.user) {
    updateAuthUI();
  } else {
    // Default to Patient demo switch on first load if not authenticated
    await demoSwitch('patient');
  }
  await loadSpecialisations();
  await loadDoctors();
  await loadNotifications();
});

// Toast Alerts
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span>
    <div>${message}</div>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// HTTP API Client
async function apiRequest(endpoint, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (state.token) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, { credentials: 'omit', ...options, headers });
    if (res.status === 401) {
      // Token expired
      console.warn('Session expired or unauthorized.');
    }
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.message || 'An error occurred');
    }
    return data;
  } catch (err) {
    showToast(err.message, 'error');
    throw err;
  }
}

// Authentication & Demo Switcher
async function demoSwitch(role) {
  try {
    const data = await apiRequest(`/auth/demo-switch/${role}`, { credentials: 'omit', method: 'POST' });
    setAuthSession(data);
    showToast(`Switched to demo persona: ${data.full_name} (${data.role.toUpperCase()})`, 'success');
    
    // Switch default tab according to role
    if (role === 'doctor') {
      switchTab('doctor-appts');
    } else if (role === 'admin') {
      switchTab('admin-dash');
    } else {
      switchTab('doctors');
    }
    await refreshActiveView();
  } catch (err) {
    console.error('Demo switch failed:', err);
  }
}

function setAuthSession(data) {
  state.token = data.access_token;
  state.user = {
    id: data.user_id,
    email: data.email,
    full_name: data.full_name,
    role: data.role,
    doctor_profile_id: data.doctor_profile_id
  };
  localStorage.setItem('cp_token', state.token);
  localStorage.setItem('cp_user', JSON.stringify(state.user));
  updateAuthUI();
}

function logout() {
  state.token = null;
  state.user = null;
  localStorage.removeItem('cp_token');
  localStorage.removeItem('cp_user');
  updateAuthUI();
  demoSwitch('patient');
}

function updateAuthUI() {
  const userNameEl = document.getElementById('navUserName');
  const userRoleEl = document.getElementById('navUserRole');
  const navTabsContainer = document.getElementById('navTabs');

  if (state.user) {
    if (userNameEl) userNameEl.textContent = state.user.full_name;
    if (userRoleEl) {
      userRoleEl.textContent = state.user.role;
      userRoleEl.className = `user-role-tag ${state.user.role}`;
    }
  }

  // Render role-specific navigation tabs
  if (navTabsContainer && state.user) {
    let tabsHtml = '';
    if (state.user.role === 'patient') {
      tabsHtml = `
        <button class="nav-tab-btn ${state.currentTab === 'doctors' ? 'active' : ''}" onclick="switchTab('doctors')">
          <span>🩺</span> Find Doctors
        </button>
        <button class="nav-tab-btn ${state.currentTab === 'patient-appts' ? 'active' : ''}" onclick="switchTab('patient-appts')">
          <span>📅</span> My Appointments & Care
        </button>
      `;
    } else if (state.user.role === 'doctor') {
      tabsHtml = `
        <button class="nav-tab-btn ${state.currentTab === 'doctor-appts' ? 'active' : ''}" onclick="switchTab('doctor-appts')">
          <span>📋</span> Appointments & AI Triage
        </button>
        <button class="nav-tab-btn ${state.currentTab === 'doctor-leaves' ? 'active' : ''}" onclick="switchTab('doctor-leaves')">
          <span>🏖️</span> Leave Management
        </button>
      `;
    } else if (state.user.role === 'admin') {
      tabsHtml = `
        <button class="nav-tab-btn ${state.currentTab === 'admin-dash' ? 'active' : ''}" onclick="switchTab('admin-dash')">
          <span>📊</span> Clinic Dashboard
        </button>
        <button class="nav-tab-btn ${state.currentTab === 'admin-doctors' ? 'active' : ''}" onclick="switchTab('admin-doctors')">
          <span>👨‍⚕️</span> Doctor Profiles
        </button>
        <button class="nav-tab-btn ${state.currentTab === 'admin-notifs' ? 'active' : ''}" onclick="switchTab('admin-notifs')">
          <span>📨</span> Notification Retry Queue
        </button>
      `;
    }
    navTabsContainer.innerHTML = tabsHtml;
  }
}

function switchTab(tabName) {
  state.currentTab = tabName;
  updateAuthUI();

  document.querySelectorAll('.view-section').forEach(sec => sec.style.display = 'none');
  const target = document.getElementById(`view-${tabName}`);
  if (target) target.style.display = 'block';

  refreshActiveView();
}

async function refreshActiveView() {
  if (state.currentTab === 'doctors') {
    await loadDoctors();
  } else if (state.currentTab === 'patient-appts') {
    await loadPatientAppointments();
  } else if (state.currentTab === 'doctor-appts') {
    await loadDoctorAppointments();
  } else if (state.currentTab === 'doctor-leaves') {
    await loadDoctorLeavesView();
  } else if (state.currentTab === 'admin-dash') {
    await loadAdminDashboard();
  } else if (state.currentTab === 'admin-doctors') {
    await loadAdminDoctors();
  } else if (state.currentTab === 'admin-notifs') {
    await loadAdminNotifications();
  }
}

// Load Specialisations
async function loadSpecialisations() {
  try {
    const list = await apiRequest('/doctors/specialisations');
    state.specialisations = ['All', ...list];
    renderSpecialisationChips();
  } catch (err) {
    console.error('Failed to load specialisations:', err);
  }
}

function renderSpecialisationChips() {
  const container = document.getElementById('specChipGroup');
  if (!container) return;

  container.innerHTML = state.specialisations.map(spec => `
    <button class="chip ${state.selectedSpecialisation === spec ? 'active' : ''}" onclick="selectSpecialisation('${spec}')">
      ${spec}
    </button>
  `).join('');
}

function selectSpecialisation(spec) {
  state.selectedSpecialisation = spec;
  renderSpecialisationChips();
  loadDoctors();
}

// Doctors Directory (Patient Portal)
async function loadDoctors() {
  try {
    let url = '/doctors?';
    if (state.selectedSpecialisation && state.selectedSpecialisation !== 'All') {
      url += `specialisation=${encodeURIComponent(state.selectedSpecialisation)}&`;
    }
    if (state.searchQuery) {
      url += `search=${encodeURIComponent(state.searchQuery)}&`;
    }

    const doctors = await apiRequest(url);
    state.doctors = doctors;
    renderDoctors();
  } catch (err) {
    console.error('Failed to load doctors:', err);
  }
}

function renderDoctors() {
  const container = document.getElementById('doctorListGrid');
  if (!container) return;

  if (state.doctors.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-secondary);">
        <h3>No doctors found matching your criteria</h3>
        <p>Try searching for a different name or specialization.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = state.doctors.map(doc => `
    <div class="card doctor-card">
      <div>
        <div class="doc-header">
          <div class="doc-avatar">${doc.full_name.replace('Dr. ', '').charAt(0)}</div>
          <div class="doc-meta">
            <h3>${doc.full_name}</h3>
            <div class="doc-spec">✦ ${doc.specialisation}</div>
          </div>
        </div>
        <p style="color: var(--text-secondary); font-size: 0.88rem; line-height: 1.5; margin-bottom: 12px;">
          ${doc.bio || 'Experienced specialist delivering patient-centered healthcare.'}
        </p>
        <ul class="doc-info-list">
          <li><span>🕒</span> Hours: ${doc.working_hours_start} - ${doc.working_hours_end} (${doc.slot_duration_minutes} min slots)</li>
          <li><span>🗓️</span> Days: ${doc.working_days.join(', ')}</li>
          ${doc.leave_days.length > 0 ? `<li style="color: var(--accent-rose)"><span>⚠️</span> On leave: ${doc.leave_days.join(', ')}</li>` : ''}
        </ul>
      </div>
      <button class="btn btn-primary" style="width: 100%; margin-top: 14px;" onclick="openBookingModal(${doc.id})">
        <span>⚡</span> Select & Book Slot
      </button>
    </div>
  `).join('');
}

// Booking Modal & Slot Hold Mechanism
async function openBookingModal(doctorId) {
  const doc = state.doctors.find(d => d.id === doctorId);
  if (!doc) return;

  state.booking.doctor = doc;
  state.booking.selectedSlot = null;
  state.booking.heldAppointmentId = null;
  state.booking.aiPreSummary = null;
  clearInterval(state.booking.holdTimerInterval);

  // Set default date to today or tomorrow
  const today = new Date();
  const dateInput = document.getElementById('bookingDateInput');
  if (dateInput) {
    dateInput.value = today.toISOString().split('T')[0];
    dateInput.min = today.toISOString().split('T')[0];
    state.booking.date = dateInput.value;
  }

  document.getElementById('bookingDocName').textContent = doc.full_name;
  document.getElementById('bookingDocSpec').textContent = `✦ ${doc.specialisation}`;
  document.getElementById('bookingSymptomInput').value = '';
  document.getElementById('aiTriagePreview').style.display = 'none';
  document.getElementById('bookingHoldTimer').style.display = 'none';

  await fetchSlotsForDate();
  openModal('bookingModal');
}

async function fetchSlotsForDate() {
  const doc = state.booking.doctor;
  const dateStr = state.booking.date;
  if (!doc || !dateStr) return;

  try {
    const data = await apiRequest(`/doctors/${doc.id}/availability?date=${dateStr}`);
    state.booking.slots = data.slots;
    renderSlotGrid(data);
  } catch (err) {
    console.error('Failed to load slots:', err);
  }
}

function renderSlotGrid(availability) {
  const container = document.getElementById('slotGridContainer');
  if (!container) return;

  if (availability.is_on_leave) {
    container.innerHTML = `<div style="grid-column: 1/-1; color: var(--accent-rose); padding: 12px; background: rgba(244,63,94,0.1); border-radius: var(--radius-sm);">Doctor is on leave on this date. Please pick another date.</div>`;
    return;
  }
  if (!availability.is_working_day) {
    container.innerHTML = `<div style="grid-column: 1/-1; color: var(--accent-amber); padding: 12px; background: rgba(245,158,11,0.1); border-radius: var(--radius-sm);">Doctor does not practice on this day of the week.</div>`;
    return;
  }
  if (availability.slots.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1; color: var(--text-secondary); padding: 12px;">No slots available for this date.</div>`;
    return;
  }

  container.innerHTML = availability.slots.map(slot => {
    const isSelected = state.booking.selectedSlot === slot.start_time;
    const disabledAttr = (!slot.is_available && !slot.is_held_by_me) ? 'disabled' : '';
    const heldClass = slot.is_held_by_me ? 'held-by-me' : '';
    const selectedClass = isSelected ? 'selected' : '';

    return `
      <button 
        class="slot-btn ${selectedClass} ${heldClass}" 
        ${disabledAttr} 
        onclick="handleSlotSelect('${slot.start_time}')"
        title="${slot.status_reason || 'Available'}"
      >
        ${slot.start_time}
      </button>
    `;
  }).join('');
}

async function handleSlotSelect(startTime) {
  // Hold slot atomically on backend
  try {
    const doc = state.booking.doctor;
    const holdData = await apiRequest('/appointments/hold', {
      method: 'POST',
      body: JSON.stringify({
        doctor_id: doc.id,
        appointment_date: state.booking.date,
        start_time: startTime
      })
    });

    state.booking.selectedSlot = startTime;
    state.booking.heldAppointmentId = holdData.appointment_id;
    state.booking.holdExpiresAt = new Date(Date.now() + holdData.hold_duration_seconds * 1000);

    showToast(`Slot ${startTime} held for 5 minutes! Complete symptom details to confirm.`, 'success');
    startHoldCountdown();
    await fetchSlotsForDate();
  } catch (err) {
    console.error('Slot hold error:', err);
  }
}

function startHoldCountdown() {
  const timerBanner = document.getElementById('bookingHoldTimer');
  const timerText = document.getElementById('holdCountdownText');
  if (!timerBanner || !timerText) return;

  timerBanner.style.display = 'flex';
  clearInterval(state.booking.holdTimerInterval);

  state.booking.holdTimerInterval = setInterval(() => {
    const remainingMs = state.booking.holdExpiresAt - new Date();
    if (remainingMs <= 0) {
      clearInterval(state.booking.holdTimerInterval);
      timerText.textContent = '00:00 (Expired)';
      showToast('Your slot hold has expired. Please reselect a slot.', 'warning');
      state.booking.selectedSlot = null;
      state.booking.heldAppointmentId = null;
      fetchSlotsForDate();
      return;
    }

    const minutes = Math.floor(remainingMs / 60000);
    const seconds = Math.floor((remainingMs % 60000) / 1000);
    timerText.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }, 1000);
}

// Pre-Visit AI Urgency Preview
async function previewAIPreVisitSummary() {
  const symptoms = document.getElementById('bookingSymptomInput').value.trim();
  if (symptoms.length < 5) {
    showToast('Please enter detailed symptoms before running AI triage.', 'warning');
    return;
  }

  const previewBox = document.getElementById('aiTriagePreview');
  const btn = document.getElementById('btnAiTriage');
  btn.disabled = true;
  btn.textContent = 'Analysing with AI...';

  try {
    const res = await apiRequest('/summaries/pre-visit-preview', {
      method: 'POST',
      body: JSON.stringify({ symptoms })
    });

    state.booking.aiPreSummary = res;
    previewBox.style.display = 'block';

    const urgencyBadge = document.getElementById('triageUrgencyBadge');
    urgencyBadge.className = `badge-urgency ${res.urgency_level}`;
    urgencyBadge.textContent = `${res.urgency_level} Urgency`;

    document.getElementById('triageChiefComplaint').textContent = res.chief_complaint;
    document.getElementById('triageQuestions').innerHTML = res.suggested_questions.map(q => `<li>${q}</li>`).join('');
  } catch (err) {
    console.error('AI preview failed:', err);
  } finally {
    btn.disabled = false;
    btn.textContent = '✨ AI Symptom Triage Preview';
  }
}

// Confirm Booking
async function submitBookingConfirmation() {
  if (!state.booking.heldAppointmentId) {
    showToast('Please select a time slot first.', 'warning');
    return;
  }
  const symptoms = document.getElementById('bookingSymptomInput').value.trim();
  if (symptoms.length < 5) {
    showToast('Please provide your symptoms before confirming.', 'warning');
    return;
  }

  const confirmBtn = document.getElementById('btnConfirmBooking');
  confirmBtn.disabled = true;
  confirmBtn.textContent = 'Confirming & Syncing...';

  try {
    const appt = await apiRequest('/appointments/confirm', {
      method: 'POST',
      body: JSON.stringify({
        appointment_id: state.booking.heldAppointmentId,
        symptoms: symptoms
      })
    });

    clearInterval(state.booking.holdTimerInterval);
    closeModal('bookingModal');
    showToast('🎉 Appointment booked successfully! Confirmation email and calendar event created.', 'success');
    
    // Open Confirmation Summary Modal with 1-click Google Calendar button
    openSuccessModal(appt);
    await loadPatientAppointments();
    await loadNotifications();
  } catch (err) {
    console.error('Confirmation error:', err);
  } finally {
    confirmBtn.disabled = false;
    confirmBtn.textContent = 'Confirm & Book Appointment';
  }
}

function openSuccessModal(appt) {
  document.getElementById('successDocName').textContent = appt.doctor_name;
  document.getElementById('successDateTime').textContent = `${appt.appointment_date} at ${appt.start_time} - ${appt.end_time}`;
  
  const gcalBtn = document.getElementById('successGCalBtn');
  if (gcalBtn && appt.google_calendar_link) {
    gcalBtn.href = appt.google_calendar_link;
  }

  const icsBtn = document.getElementById('successIcsBtn');
  if (icsBtn) {
    icsBtn.href = `/api/calendar/appointment/${appt.id}/ics`;
  }

  openModal('bookingSuccessModal');
}

// Patient Appointments View
async function loadPatientAppointments() {
  try {
    const appts = await apiRequest('/appointments/patient');
    state.appointments = appts;
    renderPatientAppointments();
  } catch (err) {
    console.error('Failed to load appointments:', err);
  }
}

function renderPatientAppointments() {
  const container = document.getElementById('patientApptsGrid');
  if (!container) return;

  if (state.appointments.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-secondary);">
        <h3>No appointments scheduled</h3>
        <p>Browse our verified specialists and book your first consultation.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = state.appointments.map(appt => {
    const isConflict = appt.status === 'reschedule_required_leave';
    return `
      <div class="card" style="${isConflict ? 'border-color: var(--accent-rose); box-shadow: 0 0 20px rgba(244,63,94,0.25);' : ''}">
        ${isConflict ? `
          <div style="background: rgba(244,63,94,0.2); color: #f43f5e; padding: 10px 14px; border-radius: var(--radius-sm); margin-bottom: 14px; font-weight: 700; font-size: 0.85rem;">
            ⚠️ ACTION REQUIRED: Doctor is on leave on this date. Please reschedule your slot.
          </div>
        ` : ''}

        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
          <div>
            <h3>${appt.doctor_name}</h3>
            <div style="color: var(--accent-cyan); font-size: 0.85rem; font-weight: 600;">${appt.doctor_specialisation || 'Specialist'}</div>
          </div>
          <span class="badge-status ${appt.status}">${appt.status.replace(/_/g, ' ')}</span>
        </div>

        <div style="color: var(--text-secondary); font-size: 0.88rem; margin-bottom: 14px; line-height: 1.6;">
          <div><strong>📅 Date:</strong> ${appt.appointment_date}</div>
          <div><strong>🕒 Time:</strong> ${appt.start_time} - ${appt.end_time}</div>
          <div><strong>📝 Symptoms:</strong> ${appt.symptoms_raw || 'None specified'}</div>
        </div>

        ${appt.ai_summary ? `
          <div class="ai-summary-card">
            <div class="ai-badge-header">
              <span style="font-size: 0.8rem; font-weight: 700; color: var(--accent-cyan);">
                <span class="ai-pulse-dot"></span> AI Pre-Visit Triage
              </span>
              <span class="badge-urgency ${appt.ai_summary.urgency_level}">${appt.ai_summary.urgency_level} Urgency</span>
            </div>
            <div style="font-size: 0.85rem; color: #cbd5e1;"><strong>Chief Complaint:</strong> ${appt.ai_summary.chief_complaint}</div>
            
            ${appt.ai_summary.patient_friendly_summary ? `
              <hr style="border: 0; border-top: 1px solid var(--border-color); margin: 10px 0;"/>
              <div style="font-size: 0.85rem; color: #34d399;"><strong>🩺 Post-Visit Care Summary:</strong></div>
              <p style="font-size: 0.83rem; color: #e2e8f0; margin-top: 4px;">${appt.ai_summary.patient_friendly_summary}</p>
              ${appt.ai_summary.medication_schedule ? `<div style="font-size: 0.8rem; color: #93c5fd; margin-top: 6px;"><strong>Rx Regimen:</strong> ${appt.ai_summary.medication_schedule}</div>` : ''}
            ` : ''}
          </div>
        ` : ''}

        ${appt.medications && appt.medications.length > 0 ? `
          <div style="margin-top: 14px; padding: 12px; background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.3); border-radius: var(--radius-sm);">
            <div style="font-size: 0.82rem; font-weight: 700; color: #34d399; margin-bottom: 6px;">💊 Active Medication Reminders</div>
            ${appt.medications.map(m => `
              <div style="font-size: 0.8rem; color: #e2e8f0;">• <strong>${m.medication_name}</strong> (${m.dosage}) - ${m.frequency} (Reminders: ${m.reminder_times.join(', ')})</div>
            `).join('')}
          </div>
        ` : ''}

        <div style="display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap;">
          ${appt.google_calendar_link ? `
            <a href="${appt.google_calendar_link}" target="_blank" class="btn btn-outline btn-sm">
              <span>📅</span> Google Calendar
            </a>
          ` : ''}
          <a href="/api/calendar/appointment/${appt.id}/ics" class="btn btn-outline btn-sm">
            <span>📥</span> Download .ICS
          </a>
          ${['confirmed', 'reschedule_required_leave'].includes(appt.status) ? `
            <button class="btn btn-emerald btn-sm" onclick="openRescheduleModal(${appt.id}, ${appt.doctor_id})">
              <span>🔄</span> Reschedule
            </button>
            <button class="btn btn-danger btn-sm" onclick="cancelAppointment(${appt.id})">
              Cancel
            </button>
          ` : ''}
        </div>
      </div>
    `;
  }).join('');
}

// Doctor Appointments Queue & AI Pre-visit Triage
async function loadDoctorAppointments() {
  try {
    const appts = await apiRequest('/appointments/doctor');
    renderDoctorQueue(appts);
  } catch (err) {
    console.error('Failed to load doctor queue:', err);
  }
}

function renderDoctorQueue(appts) {
  const container = document.getElementById('doctorQueueContainer');
  if (!container) return;

  if (appts.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
        <h3>No scheduled consultations for your profile</h3>
        <p>New patient bookings will appear here automatically with AI symptom summaries.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = appts.map(appt => `
    <div class="card" style="margin-bottom: 20px;">
      <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 14px;">
        <div>
          <h3>${appt.patient_name}</h3>
          <div style="color: var(--text-secondary); font-size: 0.85rem;">${appt.patient_email || ''}</div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
          ${appt.ai_summary ? `<span class="badge-urgency ${appt.ai_summary.urgency_level}">${appt.ai_summary.urgency_level} Urgency</span>` : ''}
          <span class="badge-status ${appt.status}">${appt.status.replace(/_/g, ' ')}</span>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 14px;">
        <div style="font-size: 0.88rem; color: var(--text-secondary);">
          <div><strong>📅 Date:</strong> ${appt.appointment_date}</div>
          <div><strong>🕒 Slot:</strong> ${appt.start_time} - ${appt.end_time}</div>
          <div style="margin-top: 8px;"><strong>Patient Stated Symptoms:</strong></div>
          <p style="color: #e2e8f0; font-size: 0.85rem; line-height: 1.4; margin-top: 4px;">${appt.symptoms_raw || 'None'}</p>
        </div>

        ${appt.ai_summary ? `
          <div class="ai-summary-card" style="margin-top: 0;">
            <div class="ai-badge-header">
              <span style="font-size: 0.8rem; font-weight: 700; color: var(--accent-cyan);">
                <span class="ai-pulse-dot"></span> AI Pre-Visit Symptom Analysis
              </span>
            </div>
            <div style="font-size: 0.85rem; color: #cbd5e1; margin-bottom: 8px;"><strong>Chief Complaint:</strong> ${appt.ai_summary.chief_complaint}</div>
            <div style="font-size: 0.8rem; font-weight: 700; color: #38bdf8; margin-bottom: 4px;">Suggested Doctor Questions:</div>
            <ul style="font-size: 0.8rem; color: #94a3b8; padding-left: 18px; line-height: 1.5;">
              ${appt.ai_summary.suggested_questions.map(q => `<li>${q}</li>`).join('')}
            </ul>
          </div>
        ` : '<div style="color: var(--text-muted); font-size: 0.85rem;">No AI analysis available.</div>'}
      </div>

      ${appt.status === 'confirmed' ? `
        <button class="btn btn-primary" onclick="openConsultationModal(${appt.id})">
          <span>🩺</span> Conduct Visit & Submit Clinical Notes
        </button>
      ` : appt.status === 'completed' ? `
        <div style="padding: 12px; background: rgba(6,182,212,0.08); border-radius: var(--radius-sm); font-size: 0.85rem;">
          <div style="color: var(--accent-cyan); font-weight: 700;">✓ Consultation Finalized</div>
          <div style="color: #cbd5e1; margin-top: 4px;"><strong>Clinical Notes:</strong> ${appt.clinical_notes_raw}</div>
          <div style="color: #34d399; margin-top: 4px;"><strong>Prescriptions:</strong> ${appt.prescription_raw}</div>
        </div>
      ` : ''}
    </div>
  `).join('');
}

// Doctor Consultation Modal & Prescription Builder
function openConsultationModal(appointmentId) {
  state.consultation.appointmentId = appointmentId;
  state.consultation.prescriptions = [
    { medication_name: 'Amoxicillin', dosage: '500mg', frequency: 'Twice Daily', duration_days: 7, instructions: 'Take with water after meals' }
  ];
  document.getElementById('clinicalNotesInput').value = 'Patient presents with symptoms of upper respiratory tract infection. Lungs clear to auscultation, no focal consolidation. Advised hydration, warm gargles, and prescribed course of antibiotics.';
  renderPrescriptionRows();
  openModal('consultationModal');
}

function addPrescriptionRow() {
  state.consultation.prescriptions.push({
    medication_name: '',
    dosage: '',
    frequency: 'Twice Daily',
    duration_days: 7,
    instructions: ''
  });
  renderPrescriptionRows();
}

function removePrescriptionRow(index) {
  state.consultation.prescriptions.splice(index, 1);
  renderPrescriptionRows();
}

function renderPrescriptionRows() {
  const container = document.getElementById('rxRowsContainer');
  if (!container) return;

  container.innerHTML = state.consultation.prescriptions.map((rx, idx) => `
    <div style="display: grid; grid-template-columns: 2fr 1fr 1.5fr 1fr auto; gap: 8px; margin-bottom: 8px; align-items: center;">
      <input type="text" class="form-input" placeholder="Medication Name" value="${rx.medication_name}" onchange="state.consultation.prescriptions[${idx}].medication_name = this.value">
      <input type="text" class="form-input" placeholder="Dosage (e.g. 500mg)" value="${rx.dosage}" onchange="state.consultation.prescriptions[${idx}].dosage = this.value">
      <select class="form-select" onchange="state.consultation.prescriptions[${idx}].frequency = this.value">
        <option value="Once Daily Morning" ${rx.frequency === 'Once Daily Morning' ? 'selected' : ''}>Once Daily (Morning)</option>
        <option value="Twice Daily" ${rx.frequency === 'Twice Daily' ? 'selected' : ''}>Twice Daily</option>
        <option value="Three Times Daily" ${rx.frequency === 'Three Times Daily' ? 'selected' : ''}>Three Times Daily</option>
        <option value="Every 8 Hours" ${rx.frequency === 'Every 8 Hours' ? 'selected' : ''}>Every 8 Hours</option>
        <option value="Once Daily Bedtime" ${rx.frequency === 'Once Daily Bedtime' ? 'selected' : ''}>Once Daily (Bedtime)</option>
      </select>
      <input type="number" class="form-input" placeholder="Days" value="${rx.duration_days}" min="1" onchange="state.consultation.prescriptions[${idx}].duration_days = parseInt(this.value) || 7">
      <button type="button" class="btn btn-danger btn-sm" onclick="removePrescriptionRow(${idx})">✕</button>
    </div>
  `).join('');
}

async function submitConsultation() {
  const clinicalNotes = document.getElementById('clinicalNotesInput').value.trim();
  if (clinicalNotes.length < 5) {
    showToast('Please enter detailed clinical notes.', 'warning');
    return;
  }

  const btn = document.getElementById('btnSubmitConsultation');
  btn.disabled = true;
  btn.textContent = 'Generating AI Care Plan & Finalizing...';

  try {
    await apiRequest(`/appointments/${state.consultation.appointmentId}/complete`, {
      method: 'POST',
      body: JSON.stringify({
        clinical_notes: clinicalNotes,
        prescriptions: state.consultation.prescriptions.filter(p => p.medication_name.trim())
      })
    });

    closeModal('consultationModal');
    showToast('Consultation completed! AI patient-friendly summary & medication reminder schedule created.', 'success');
    await loadDoctorAppointments();
  } catch (err) {
    console.error('Submit consultation error:', err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Finalize Consultation & Generate AI Summary';
  }
}

// Doctor Leave Management View
async function loadDoctorLeavesView() {
  const container = document.getElementById('doctorLeaveContainer');
  if (!container) return;

  if (!state.user || !state.user.doctor_profile_id) {
    container.innerHTML = `<div style="color: var(--text-secondary); padding: 20px;">Doctor profile not linked.</div>`;
    return;
  }

  const doc = await apiRequest(`/doctors/${state.user.doctor_profile_id}`);
  container.innerHTML = `
    <div class="card" style="max-width: 700px; margin: 0 auto;">
      <h3 style="margin-bottom: 8px;">Manage Scheduled Leaves</h3>
      <p style="color: var(--text-secondary); font-size: 0.88rem; margin-bottom: 20px;">
        When you register a leave date, the system automatically checks for conflicting bookings, flags them for rescheduling, and dispatches immediate notification alerts to affected patients.
      </p>

      <div class="form-group">
        <label class="form-label">Select Leave Date</label>
        <div style="display: flex; gap: 10px;">
          <input type="date" id="leaveDatePicker" class="form-input" min="${new Date().toISOString().split('T')[0]}">
          <button class="btn btn-primary" onclick="submitDoctorLeave()">Add Leave Day</button>
        </div>
      </div>

      <h4 style="margin: 24px 0 12px;">Registered Leave Dates</h4>
      ${doc.leave_days.length === 0 ? '<p style="color: var(--text-muted); font-size: 0.85rem;">No upcoming leave days registered.</p>' : `
        <div style="display: flex; flex-direction: column; gap: 8px;">
          ${doc.leave_days.map(d => `
            <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(30,41,59,0.7); padding: 10px 16px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
              <span>🏖️ ${d}</span>
              <button class="btn btn-danger btn-sm" onclick="deleteDoctorLeave('${d}')">Remove</button>
            </div>
          `).join('')}
        </div>
      `}
    </div>
  `;
}

async function submitDoctorLeave() {
  const dateInput = document.getElementById('leaveDatePicker');
  if (!dateInput || !dateInput.value) {
    showToast('Please select a leave date.', 'warning');
    return;
  }

  try {
    const res = await apiRequest(`/doctors/${state.user.doctor_profile_id}/leave`, {
      method: 'POST',
      body: JSON.stringify({ leave_dates: [dateInput.value] })
    });

    if (res.conflicts_count > 0) {
      showToast(`Leave registered! ${res.conflicts_count} existing booking(s) detected and automatically notified for rescheduling.`, 'warning');
    } else {
      showToast('Leave date added successfully. No existing bookings affected.', 'success');
    }
    await loadDoctorLeavesView();
  } catch (err) {
    console.error('Failed to submit leave:', err);
  }
}

async function deleteDoctorLeave(dateStr) {
  try {
    await apiRequest(`/doctors/${state.user.doctor_profile_id}/leave/${dateStr}`, { method: 'DELETE' });
    showToast(`Leave on ${dateStr} removed.`, 'success');
    await loadDoctorLeavesView();
  } catch (err) {
    console.error('Failed to delete leave:', err);
  }
}

// Admin Portal Views
async function loadAdminDashboard() {
  try {
    const metrics = await apiRequest('/admin/dashboard');
    state.adminMetrics = metrics;
    renderAdminDashboard(metrics);
  } catch (err) {
    console.error('Failed to load admin metrics:', err);
  }
}

function renderAdminDashboard(m) {
  const container = document.getElementById('adminDashContainer');
  if (!container) return;

  container.innerHTML = `
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 24px;">
      <div class="card" style="border-left: 4px solid var(--accent-cyan);">
        <div style="color: var(--text-secondary); font-size: 0.85rem;">Total Appointments</div>
        <div style="font-size: 2rem; font-weight: 800; color: #fff; margin-top: 4px;">${m.total_appointments}</div>
      </div>
      <div class="card" style="border-left: 4px solid var(--accent-emerald);">
        <div style="color: var(--text-secondary); font-size: 0.85rem;">Active Doctors</div>
        <div style="font-size: 2rem; font-weight: 800; color: #34d399; margin-top: 4px;">${m.total_doctors}</div>
      </div>
      <div class="card" style="border-left: 4px solid var(--accent-purple);">
        <div style="color: var(--text-secondary); font-size: 0.85rem;">Registered Patients</div>
        <div style="font-size: 2rem; font-weight: 800; color: #a78bfa; margin-top: 4px;">${m.total_patients}</div>
      </div>
      <div class="card" style="border-left: 4px solid var(--accent-rose);">
        <div style="color: var(--text-secondary); font-size: 0.85rem;">Pending Conflict Reschedules</div>
        <div style="font-size: 2rem; font-weight: 800; color: #f43f5e; margin-top: 4px;">${m.conflict_reschedules_needed}</div>
      </div>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
      <div class="card">
        <h3 style="margin-bottom: 14px;">Appointment Status Breakdown</h3>
        <ul style="list-style: none; display: flex; flex-direction: column; gap: 8px;">
          ${Object.entries(m.appointment_status_breakdown || {}).map(([st, cnt]) => `
            <li style="display: flex; justify-content: space-between; padding: 6px 12px; background: rgba(30,41,59,0.5); border-radius: var(--radius-sm);">
              <span class="badge-status ${st}">${st.replace(/_/g, ' ')}</span>
              <strong>${cnt}</strong>
            </li>
          `).join('')}
        </ul>
      </div>

      <div class="card">
        <h3 style="margin-bottom: 14px;">AI Triage Urgency Distribution</h3>
        <ul style="list-style: none; display: flex; flex-direction: column; gap: 8px;">
          ${Object.entries(m.ai_urgency_breakdown || {}).map(([urg, cnt]) => `
            <li style="display: flex; justify-content: space-between; padding: 6px 12px; background: rgba(30,41,59,0.5); border-radius: var(--radius-sm);">
              <span class="badge-urgency ${urg}">${urg} Urgency</span>
              <strong>${cnt}</strong>
            </li>
          `).join('')}
        </ul>
      </div>
    </div>

    <div class="card" style="margin-top: 24px;">
      <h3 style="margin-bottom: 12px;">Background Engine Simulator & Manual Triggers</h3>
      <p style="color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 16px;">
        Trigger real-time scheduled background jobs manually for immediate testing:
      </p>
      <div style="display: flex; gap: 12px; flex-wrap: wrap;">
        <button class="btn btn-outline btn-sm" onclick="triggerBackgroundJob('cleanup-holds')">
          🧹 Purge Expired Slot Holds
        </button>
        <button class="btn btn-outline btn-sm" onclick="triggerBackgroundJob('medication-reminders')">
          💊 Dispatch Medication Reminders
        </button>
        <button class="btn btn-outline btn-sm" onclick="triggerBackgroundJob('retry-notifications')">
          🔁 Process Notification Retry Queue
        </button>
      </div>
    </div>
  `;
}

async function triggerBackgroundJob(jobName) {
  try {
    const res = await apiRequest(`/admin/trigger-background/${jobName}`, { method: 'POST' });
    showToast(res.message, 'success');
    await loadAdminDashboard();
  } catch (err) {
    console.error('Trigger job failed:', err);
  }
}

async function loadAdminDoctors() {
  const container = document.getElementById('adminDoctorsContainer');
  if (!container) return;

  const doctors = await apiRequest('/doctors');
  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <h3>Doctor Profiles Management</h3>
      <button class="btn btn-primary" onclick="openModal('createDoctorModal')">+ Create New Doctor</button>
    </div>
    <div class="grid-cards">
      ${doctors.map(d => `
        <div class="card">
          <div class="doc-header">
            <div class="doc-avatar">${d.full_name.charAt(0)}</div>
            <div class="doc-meta">
              <h3>${d.full_name}</h3>
              <div class="doc-spec">✦ ${d.specialisation}</div>
              <div style="font-size: 0.8rem; color: var(--text-secondary);">${d.email}</div>
            </div>
          </div>
          <div style="font-size: 0.85rem; color: var(--text-secondary); margin: 10px 0;">
            <div>🕒 Hours: ${d.working_hours_start} - ${d.working_hours_end} (${d.slot_duration_minutes} min)</div>
            <div>🗓️ Days: ${d.working_days.join(', ')}</div>
            <div>🏖️ Leaves: ${d.leave_days.length} day(s)</div>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

async function submitCreateDoctor() {
  const email = document.getElementById('newDocEmail').value.trim();
  const password = document.getElementById('newDocPassword').value.trim();
  const fullName = document.getElementById('newDocName').value.trim();
  const specialisation = document.getElementById('newDocSpec').value.trim();
  const hoursStart = document.getElementById('newDocStart').value.trim();
  const hoursEnd = document.getElementById('newDocEnd').value.trim();
  const slotDuration = parseInt(document.getElementById('newDocSlotDuration').value) || 30;

  try {
    await apiRequest('/admin/doctors', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        full_name: fullName,
        specialisation,
        working_hours_start: hoursStart,
        working_hours_end: hoursEnd,
        slot_duration_minutes: slotDuration
      })
    });
    closeModal('createDoctorModal');
    showToast(`Doctor ${fullName} created successfully!`, 'success');
    await loadAdminDoctors();
  } catch (err) {
    console.error('Create doctor error:', err);
  }
}

async function loadAdminNotifications() {
  const container = document.getElementById('adminNotifsContainer');
  if (!container) return;

  const notifs = await apiRequest('/admin/notifications');
  container.innerHTML = `
    <div class="card">
      <h3 style="margin-bottom: 16px;">Notification Dispatch & Retry Queue Log</h3>
      <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem; text-align: left;">
          <thead>
            <tr style="border-bottom: 1px solid var(--border-color); color: var(--text-secondary);">
              <th style="padding: 10px;">ID</th>
              <th style="padding: 10px;">Type</th>
              <th style="padding: 10px;">Recipient</th>
              <th style="padding: 10px;">Subject</th>
              <th style="padding: 10px;">Status</th>
              <th style="padding: 10px;">Retries</th>
              <th style="padding: 10px;">Action</th>
            </tr>
          </thead>
          <tbody>
            ${notifs.map(n => `
              <tr style="border-bottom: 1px solid rgba(51,65,85,0.3);">
                <td style="padding: 10px;">#${n.id}</td>
                <td style="padding: 10px;">${n.notification_type}</td>
                <td style="padding: 10px;">User #${n.recipient_id}</td>
                <td style="padding: 10px;">${n.subject}</td>
                <td style="padding: 10px;"><span class="badge-status ${n.status}">${n.status}</span></td>
                <td style="padding: 10px;">${n.retry_count} / ${n.max_retries}</td>
                <td style="padding: 10px;">
                  ${['failed', 'retrying'].includes(n.status) ? `
                    <button class="btn btn-emerald btn-sm" onclick="retryNotification(${n.id})">Retry</button>
                  ` : '—'}
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

async function retryNotification(notifId) {
  try {
    const res = await apiRequest(`/admin/notifications/${notifId}/retry`, { method: 'POST' });
    showToast(`Notification #${notifId} retry triggered. Result: ${res.status}`, 'success');
    await loadAdminNotifications();
  } catch (err) {
    console.error('Retry notification error:', err);
  }
}

// Notifications Bell & Drawer
async function loadNotifications() {
  if (!state.token) return;
  try {
    const notifs = await apiRequest('/notifications/my');
    state.notifications = notifs;
    
    const countEl = document.getElementById('notifCountBadge');
    if (countEl) {
      countEl.textContent = notifs.length;
      countEl.style.display = notifs.length > 0 ? 'flex' : 'none';
    }
  } catch (err) {
    console.error('Failed to load notifications:', err);
  }
}

function toggleNotificationDrawer() {
  const drawer = document.getElementById('notificationDrawer');
  if (!drawer) return;

  const isOpen = drawer.classList.contains('open');
  if (isOpen) {
    drawer.classList.remove('open');
  } else {
    renderNotificationDrawer();
    drawer.classList.add('open');
  }
}

function renderNotificationDrawer() {
  const container = document.getElementById('notificationList');
  if (!container) return;

  if (state.notifications.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 20px;">No notifications yet.</div>`;
    return;
  }

  container.innerHTML = state.notifications.map(n => `
    <div style="background: rgba(30,41,59,0.7); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 12px; margin-bottom: 10px;">
      <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--accent-cyan); font-weight: 700; margin-bottom: 4px;">
        <span>${n.notification_type.toUpperCase().replace(/_/g, ' ')}</span>
        <span>${new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
      </div>
      <div style="font-size: 0.88rem; font-weight: 600; color: #fff; margin-bottom: 4px;">${n.subject}</div>
      <div style="font-size: 0.8rem; color: var(--text-secondary);">${n.body.replace(/<[^>]*>?/gm, '')}</div>
    </div>
  `).join('');
}

// Reschedule & Cancel Handlers
async function cancelAppointment(appointmentId) {
  if (!confirm('Are you sure you want to cancel this appointment? Both parties will be notified.')) return;

  try {
    await apiRequest(`/appointments/${appointmentId}/cancel`, { method: 'POST' });
    showToast('Appointment cancelled.', 'info');
    await loadPatientAppointments();
    await loadNotifications();
  } catch (err) {
    console.error('Cancel appointment error:', err);
  }
}

function openRescheduleModal(appointmentId, doctorId) {
  state.booking.rescheduleAppointmentId = appointmentId;
  const dateInput = document.getElementById('rescheduleDateInput');
  if (dateInput) {
    dateInput.value = new Date().toISOString().split('T')[0];
    dateInput.min = new Date().toISOString().split('T')[0];
  }
  openModal('rescheduleModal');
}

async function submitReschedule() {
  const newDate = document.getElementById('rescheduleDateInput').value;
  const newTime = document.getElementById('rescheduleTimeInput').value;
  if (!newDate || !newTime) {
    showToast('Please select both a new date and time.', 'warning');
    return;
  }

  try {
    await apiRequest(`/appointments/${state.booking.rescheduleAppointmentId}/reschedule`, {
      method: 'POST',
      body: JSON.stringify({ new_date: newDate, new_start_time: newTime })
    });
    closeModal('rescheduleModal');
    showToast('Appointment rescheduled successfully! Calendar and notifications updated.', 'success');
    await loadPatientAppointments();
  } catch (err) {
    console.error('Reschedule error:', err);
  }
}

// Generic Modal Helpers
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add('open');
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('open');
}

function initUIEventListeners() {
  const searchInput = document.getElementById('doctorSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      state.searchQuery = e.target.value;
      loadDoctors();
    });
  }

  const bookingDateInput = document.getElementById('bookingDateInput');
  if (bookingDateInput) {
    bookingDateInput.addEventListener('change', (e) => {
      state.booking.date = e.target.value;
      state.booking.selectedSlot = null;
      state.booking.heldAppointmentId = null;
      clearInterval(state.booking.holdTimerInterval);
      document.getElementById('bookingHoldTimer').style.display = 'none';
      fetchSlotsForDate();
    });
  }
}
