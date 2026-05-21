import { writable } from 'svelte/store';
import { currentMonthKey } from '$utils/dates';

export const selectedMonth = writable(currentMonthKey());
