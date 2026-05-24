<script lang="ts">
	import Apple from '@lucide/svelte/icons/apple';
	import Baby from '@lucide/svelte/icons/baby';
	import Banana from '@lucide/svelte/icons/banana';
	import Banknote from '@lucide/svelte/icons/banknote';
	import Bed from '@lucide/svelte/icons/bed';
	import Beef from '@lucide/svelte/icons/beef';
	import Beer from '@lucide/svelte/icons/beer';
	import Bell from '@lucide/svelte/icons/bell';
	import Bike from '@lucide/svelte/icons/bike';
	import Book from '@lucide/svelte/icons/book';
	import Briefcase from '@lucide/svelte/icons/briefcase';
	import Brush from '@lucide/svelte/icons/brush';
	import Building2 from '@lucide/svelte/icons/building-2';
	import Bus from '@lucide/svelte/icons/bus';
	import Cake from '@lucide/svelte/icons/cake';
	import Calendar from '@lucide/svelte/icons/calendar';
	import Camera from '@lucide/svelte/icons/camera';
	import Car from '@lucide/svelte/icons/car';
	import Carrot from '@lucide/svelte/icons/carrot';
	import Cat from '@lucide/svelte/icons/cat';
	import CircleHelp from '@lucide/svelte/icons/circle-help';
	import Clock from '@lucide/svelte/icons/clock';
	import Cloud from '@lucide/svelte/icons/cloud';
	import Coffee from '@lucide/svelte/icons/coffee';
	import Coins from '@lucide/svelte/icons/coins';
	import Cookie from '@lucide/svelte/icons/cookie';
	import CreditCard from '@lucide/svelte/icons/credit-card';
	import CupSoda from '@lucide/svelte/icons/cup-soda';
	import Dog from '@lucide/svelte/icons/dog';
	import Droplets from '@lucide/svelte/icons/droplets';
	import Dumbbell from '@lucide/svelte/icons/dumbbell';
	import Film from '@lucide/svelte/icons/film';
	import Flag from '@lucide/svelte/icons/flag';
	import Flame from '@lucide/svelte/icons/flame';
	import Flower from '@lucide/svelte/icons/flower';
	import Fuel from '@lucide/svelte/icons/fuel';
	import Fish from '@lucide/svelte/icons/fish';
	import Gamepad2 from '@lucide/svelte/icons/gamepad-2';
	import Gift from '@lucide/svelte/icons/gift';
	import GraduationCap from '@lucide/svelte/icons/graduation-cap';
	import Hammer from '@lucide/svelte/icons/hammer';
	import HandCoins from '@lucide/svelte/icons/hand-coins';
	import Headphones from '@lucide/svelte/icons/headphones';
	import HeartPulse from '@lucide/svelte/icons/heart-pulse';
	import House from '@lucide/svelte/icons/house';
	import IceCreamBowl from '@lucide/svelte/icons/ice-cream-bowl';
	import Key from '@lucide/svelte/icons/key';
	import Landmark from '@lucide/svelte/icons/landmark';
	import Laptop from '@lucide/svelte/icons/laptop';
	import Leaf from '@lucide/svelte/icons/leaf';
	import Lock from '@lucide/svelte/icons/lock';
	import MapPin from '@lucide/svelte/icons/map-pin';
	import Martini from '@lucide/svelte/icons/martini';
	import Monitor from '@lucide/svelte/icons/monitor';
	import Moon from '@lucide/svelte/icons/moon';
	import Mountain from '@lucide/svelte/icons/mountain';
	import Music from '@lucide/svelte/icons/music';
	import Package from '@lucide/svelte/icons/package';
	import PaintBucket from '@lucide/svelte/icons/paint-bucket';
	import Palette from '@lucide/svelte/icons/palette';
	import PawPrint from '@lucide/svelte/icons/paw-print';
	import PiggyBank from '@lucide/svelte/icons/piggy-bank';
	import Pill from '@lucide/svelte/icons/pill';
	import Pizza from '@lucide/svelte/icons/pizza';
	import Plane from '@lucide/svelte/icons/plane';
	import Popcorn from '@lucide/svelte/icons/popcorn';
	import Receipt from '@lucide/svelte/icons/receipt';
	import Sandwich from '@lucide/svelte/icons/sandwich';
	import Scissors from '@lucide/svelte/icons/scissors';
	import Shield from '@lucide/svelte/icons/shield';
	import Shirt from '@lucide/svelte/icons/shirt';
	import ShoppingBag from '@lucide/svelte/icons/shopping-bag';
	import ShoppingCart from '@lucide/svelte/icons/shopping-cart';
	import Smartphone from '@lucide/svelte/icons/smartphone';
	import Snowflake from '@lucide/svelte/icons/snowflake';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import Star from '@lucide/svelte/icons/star';
	import Stethoscope from '@lucide/svelte/icons/stethoscope';
	import Sun from '@lucide/svelte/icons/sun';
	import Tag from '@lucide/svelte/icons/tag';
	import TrainFront from '@lucide/svelte/icons/train-front';
	import Trophy from '@lucide/svelte/icons/trophy';
	import Truck from '@lucide/svelte/icons/truck';
	import Tv from '@lucide/svelte/icons/tv';
	import Umbrella from '@lucide/svelte/icons/umbrella';
	import Utensils from '@lucide/svelte/icons/utensils';
	import Wallet from '@lucide/svelte/icons/wallet';
	import Wifi from '@lucide/svelte/icons/wifi';
	import Wine from '@lucide/svelte/icons/wine';
	import Wrench from '@lucide/svelte/icons/wrench';
	import Zap from '@lucide/svelte/icons/zap';
	import { normalizeCategoryIcon } from '$utils/categoryIcons';

	let {
		name,
		size = 18,
		strokeWidth = 2.25
	}: { name?: string; size?: number; strokeWidth?: number } = $props();

	const iconName = $derived(normalizeCategoryIcon(name));
</script>

{#if iconName === 'shopping-cart'}
	<ShoppingCart {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'shopping-bag'}
	<ShoppingBag {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'utensils'}
	<Utensils {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'coffee'}
	<Coffee {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'pizza'}
	<Pizza {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'sandwich'}
	<Sandwich {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'wine'}
	<Wine {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'beer'}
	<Beer {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'martini'}
	<Martini {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'cup-soda'}
	<CupSoda {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'ice-cream-bowl'}
	<IceCreamBowl {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'cookie'}
	<Cookie {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'cake'}
	<Cake {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'popcorn'}
	<Popcorn {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'apple'}
	<Apple {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'banana'}
	<Banana {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'carrot'}
	<Carrot {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'fish'}
	<Fish {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'beef'}
	<Beef {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'car'}
	<Car {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'fuel'}
	<Fuel {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'train-front'}
	<TrainFront {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'bus'}
	<Bus {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'bike'}
	<Bike {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'plane'}
	<Plane {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'truck'}
	<Truck {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'map-pin'}
	<MapPin {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'house'}
	<House {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'building-2'}
	<Building2 {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'landmark'}
	<Landmark {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'bed'}
	<Bed {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'wrench'}
	<Wrench {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'hammer'}
	<Hammer {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'paint-bucket'}
	<PaintBucket {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'zap'}
	<Zap {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'flame'}
	<Flame {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'droplets'}
	<Droplets {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'wifi'}
	<Wifi {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'smartphone'}
	<Smartphone {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'tv'}
	<Tv {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'monitor'}
	<Monitor {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'laptop'}
	<Laptop {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'headphones'}
	<Headphones {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'gamepad-2'}
	<Gamepad2 {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'music'}
	<Music {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'film'}
	<Film {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'camera'}
	<Camera {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'receipt'}
	<Receipt {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'wallet'}
	<Wallet {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'credit-card'}
	<CreditCard {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'banknote'}
	<Banknote {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'coins'}
	<Coins {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'hand-coins'}
	<HandCoins {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'piggy-bank'}
	<PiggyBank {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'shield'}
	<Shield {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'briefcase'}
	<Briefcase {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'heart-pulse'}
	<HeartPulse {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'stethoscope'}
	<Stethoscope {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'pill'}
	<Pill {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'dumbbell'}
	<Dumbbell {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'baby'}
	<Baby {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'dog'}
	<Dog {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'cat'}
	<Cat {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'paw-print'}
	<PawPrint {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'shirt'}
	<Shirt {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'scissors'}
	<Scissors {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'brush'}
	<Brush {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'palette'}
	<Palette {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'book'}
	<Book {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'graduation-cap'}
	<GraduationCap {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'flower'}
	<Flower {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'leaf'}
	<Leaf {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'sun'}
	<Sun {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'moon'}
	<Moon {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'cloud'}
	<Cloud {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'snowflake'}
	<Snowflake {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'umbrella'}
	<Umbrella {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'mountain'}
	<Mountain {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'gift'}
	<Gift {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'sparkles'}
	<Sparkles {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'star'}
	<Star {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'trophy'}
	<Trophy {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'flag'}
	<Flag {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'bell'}
	<Bell {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'clock'}
	<Clock {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'calendar'}
	<Calendar {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'tag'}
	<Tag {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'package'}
	<Package {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'key'}
	<Key {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'lock'}
	<Lock {size} {strokeWidth} aria-hidden="true" />
{:else}
	<CircleHelp {size} {strokeWidth} aria-hidden="true" />
{/if}
