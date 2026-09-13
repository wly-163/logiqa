<template>
  <div style="max-width:520px;margin:0 auto">
    <div class="card">
      <div class="card-header"><h3 class="card-title">{{ t('profile.title') }}</h3></div>
      <div v-if="p" style="display:flex;flex-direction:column;gap:14px;margin-top:8px">
        <div class="cause" style="justify-content:space-between"><span>{{ t('profile.username') }}</span><b>{{ p.username }}</b></div>
        <div class="cause" style="justify-content:space-between"><span>{{ t('profile.role') }}</span><span class="badge badge-neutral">{{ t('role.' + p.role) }}</span></div>
        <div class="cause" style="justify-content:space-between"><span>{{ t('profile.tenant') }}</span><span class="muted">{{ p.tenantId }}</span></div>
        <div class="cause" style="justify-content:space-between"><span>{{ t('profile.status') }}</span><span class="badge" :class="p.status==='inactive'?'badge-danger':'badge-success'">{{ p.status==='inactive'? t('profile.disabled') : t('profile.ok') }}</span></div>
        <div class="cause" style="justify-content:space-between"><span>{{ t('profile.created') }}</span><span class="muted">{{ p.createdAt }}</span></div>
        <div>
          <label class="hint">{{ t('profile.dept') }}</label>
          <div class="row" style="gap:8px;margin-top:6px">
            <input class="input" v-model="dept" :placeholder="t('profile.deptPh')" />
            <button class="btn btn-primary" @click="saveDept">{{ t('profile.saveDept') }}</button>
          </div>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:14px">
      <div class="card-header"><h3 class="card-title">{{ t('profile.pwd') }}</h3></div>
      <div style="display:flex;flex-direction:column;gap:10px;margin-top:8px">
        <input class="input" type="password" v-model="pwd.old" :placeholder="t('profile.old')" />
        <input class="input" type="password" v-model="pwd.new1" :placeholder="t('profile.new1')" />
        <input class="input" type="password" v-model="pwd.new2" :placeholder="t('profile.new2')" />
        <button class="btn btn-primary" @click="savePwd">{{ t('profile.change') }}</button>
      </div>
    </div>
    <div class="toast" v-if="msg">{{ msg }}</div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getProfile, updateProfile, changePassword } from '../api'
const { t } = useI18n()
const p = ref(null)
const dept = ref('')
const pwd = reactive({ old: '', new1: '', new2: '' })
const msg = ref('')
let timer = null
function toast(m) { msg.value = m; clearTimeout(timer); timer = setTimeout(() => msg.value = '', 1800) }
async function load() { try { p.value = (await getProfile()).data; dept.value = p.value.dept || '' } catch (e) { toast(t('profile.loadFail')) } }
async function saveDept() { try { await updateProfile(dept.value); toast(t('profile.deptOk')); load() } catch (e) { toast(t('profile.saveFail')) } }
async function savePwd() {
  if (!pwd.old) { toast(t('profile.needOld')); return }
  if (pwd.new1.length < 6) { toast(t('profile.pwdLen')); return }
  if (pwd.new1 !== pwd.new2) { toast(t('profile.pwdMismatch')); return }
  try { await changePassword(pwd.old, pwd.new1); toast(t('profile.pwdOk')); pwd.old = pwd.new1 = pwd.new2 = '' }
  catch (e) { toast(t('profile.pwdFail')) }
}
onMounted(load)
</script>
