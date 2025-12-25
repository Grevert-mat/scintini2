CREATE TABLE `karaoke_rooms` (
	`id` int AUTO_INCREMENT NOT NULL,
	`roomCode` varchar(8) NOT NULL,
	`name` varchar(255) NOT NULL,
	`createdBy` int NOT NULL,
	`isActive` boolean NOT NULL DEFAULT true,
	`currentVideoId` varchar(255),
	`currentVideoTitle` varchar(500),
	`currentVideoThumbnail` text,
	`isPlaying` boolean NOT NULL DEFAULT false,
	`currentTime` int NOT NULL DEFAULT 0,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `karaoke_rooms_id` PRIMARY KEY(`id`),
	CONSTRAINT `karaoke_rooms_roomCode_unique` UNIQUE(`roomCode`)
);
--> statement-breakpoint
CREATE TABLE `play_history` (
	`id` int AUTO_INCREMENT NOT NULL,
	`roomId` int NOT NULL,
	`videoId` varchar(255) NOT NULL,
	`title` varchar(500) NOT NULL,
	`artist` varchar(255),
	`addedBy` int NOT NULL,
	`playedAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `play_history_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `room_participants` (
	`id` int AUTO_INCREMENT NOT NULL,
	`roomId` int NOT NULL,
	`userId` int NOT NULL,
	`joinedAt` timestamp NOT NULL DEFAULT (now()),
	`lastActivity` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `room_participants_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `song_queue` (
	`id` int AUTO_INCREMENT NOT NULL,
	`roomId` int NOT NULL,
	`videoId` varchar(255) NOT NULL,
	`title` varchar(500) NOT NULL,
	`artist` varchar(255),
	`thumbnail` text,
	`duration` int,
	`addedBy` int NOT NULL,
	`position` int NOT NULL,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `song_queue_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
ALTER TABLE `users` ADD `youtubeAccessToken` text;--> statement-breakpoint
ALTER TABLE `users` ADD `youtubeRefreshToken` text;