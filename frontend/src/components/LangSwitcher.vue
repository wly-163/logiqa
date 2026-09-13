<template>
  <select class="select lang-switch" :value="locale" :title="t('lang.label')" @change="onChange">
    <option v-for="item in LOCALES" :key="item.value" :value="item.value">{{ item.native }}</option>
  </select>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { LOCALES, setLocale } from '../i18n'

const { locale, t } = useI18n()
function onChange(e) { setLocale(e.target.value) }
</script>

<style scoped>
.lang-switch { width: auto; min-width: 108px; font-size: 12px; padding: 5px 8px; }
</style>
