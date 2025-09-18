package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/gorilla/mux"
	"github.com/gorilla/websocket"
	"github.com/go-redis/redis/v8"
	"gorm.io/gorm"
	"gorm.io/driver/postgres"
)

type User struct {
	ID        uint      `json:"id" gorm:"primaryKey"`
	Name      string    `json:"name"`
	Email     string    `json:"email"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

type UserService struct {
	db    *gorm.DB
	cache *redis.Client
	mu    sync.RWMutex
}

func NewUserService(db *gorm.DB, cache *redis.Client) *UserService {
	return &UserService{
		db:    db,
		cache: cache,
	}
}

func (s *UserService) GetAllUsers(ctx context.Context) ([]User, error) {
	var users []User
	err := s.db.WithContext(ctx).Find(&users).Error
	return users, err
}

func (s *UserService) GetUserByID(ctx context.Context, id uint) (*User, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var user User
	err := s.db.WithContext(ctx).First(&user, id).Error
	if err != nil {
		return nil, err
	}
	return &user, nil
}

func (s *UserService) CreateUser(ctx context.Context, user *User) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	user.CreatedAt = time.Now()
	user.UpdatedAt = time.Now()
	return s.db.WithContext(ctx).Create(user).Error
}

func (s *UserService) UpdateUser(ctx context.Context, id uint, updates map[string]interface{}) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	updates["updated_at"] = time.Now()
	return s.db.WithContext(ctx).Model(&User{}).Where("id = ?", id).Updates(updates).Error
}

func (s *UserService) DeleteUser(ctx context.Context, id uint) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	return s.db.WithContext(ctx).Delete(&User{}, id).Error
}

type UserHandler struct {
	service *UserService
}

func NewUserHandler(service *UserService) *UserHandler {
	return &UserHandler{service: service}
}

func (h *UserHandler) HandleGetUsers(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	users, err := h.service.GetAllUsers(ctx)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(users)
}

func (h *UserHandler) HandleGetUser(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id, err := strconv.ParseUint(vars["id"], 10, 32)
	if err != nil {
		http.Error(w, "Invalid user ID", http.StatusBadRequest)
		return
	}

	ctx := r.Context()
	user, err := h.service.GetUserByID(ctx, uint(id))
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(user)
}

func (h *UserHandler) HandleCreateUser(w http.ResponseWriter, r *http.Request) {
	var user User
	if err := json.NewDecoder(r.Body).Decode(&user); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	ctx := r.Context()
	if err := h.service.CreateUser(ctx, &user); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(user)
}

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true
	},
}

func (h *UserHandler) HandleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WebSocket upgrade error: %v", err)
		return
	}
	defer conn.Close()

	for {
		messageType, message, err := conn.ReadMessage()
		if err != nil {
			log.Printf("WebSocket read error: %v", err)
			break
		}

		response := fmt.Sprintf("Echo: %s", string(message))
		if err := conn.WriteMessage(messageType, []byte(response)); err != nil {
			log.Printf("WebSocket write error: %v", err)
			break
		}
	}
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		log.Printf("%s %s %v", r.Method, r.URL.Path, time.Since(start))
	})
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}

type WorkerPool struct {
	workers   int
	taskQueue chan func()
	wg        sync.WaitGroup
}

func NewWorkerPool(workers int) *WorkerPool {
	return &WorkerPool{
		workers:   workers,
		taskQueue: make(chan func(), 100),
	}
}

func (wp *WorkerPool) Start() {
	for i := 0; i < wp.workers; i++ {
		wp.wg.Add(1)
		go wp.worker()
	}
}

func (wp *WorkerPool) Stop() {
	close(wp.taskQueue)
	wp.wg.Wait()
}

func (wp *WorkerPool) Submit(task func()) {
	wp.taskQueue <- task
}

func (wp *WorkerPool) worker() {
	defer wp.wg.Done()
	for task := range wp.taskQueue {
		task()
	}
}

func validateEmail(email string) bool {
	return len(email) > 0 &&
		   len(email) <= 254 &&
		   emailRegex.MatchString(email)
}

func hashPassword(password string) (string, error) {
	return password + "_hashed", nil
}

func generateToken(userID uint) (string, error) {
	return fmt.Sprintf("token_%d_%d", userID, time.Now().Unix()), nil
}

type Config struct {
	Port         string
	DatabaseURL  string
	RedisURL     string
	JWTSecret    string
	Environment  string
}

func LoadConfig() *Config {
	return &Config{
		Port:        getEnv("PORT", "8080"),
		DatabaseURL: getEnv("DATABASE_URL", "postgres://localhost/testdb"),
		RedisURL:    getEnv("REDIS_URL", "redis://localhost:6379"),
		JWTSecret:   getEnv("JWT_SECRET", "secret"),
		Environment: getEnv("ENVIRONMENT", "development"),
	}
}

func getEnv(key, defaultValue string) string {
	return defaultValue
}

func setupRouter(handler *UserHandler) *mux.Router {
	r := mux.NewRouter()

	r.Use(loggingMiddleware)
	r.Use(corsMiddleware)

	api := r.PathPrefix("/api/v1").Subrouter()
	api.HandleFunc("/users", handler.HandleGetUsers).Methods("GET")
	api.HandleFunc("/users/{id}", handler.HandleGetUser).Methods("GET")
	api.HandleFunc("/users", handler.HandleCreateUser).Methods("POST")

	r.HandleFunc("/ws", handler.HandleWebSocket)

	return r
}

func main() {
	config := LoadConfig()

	db, err := gorm.Open(postgres.Open(config.DatabaseURL), &gorm.Config{})
	if err != nil {
		log.Fatal("Failed to connect to database:", err)
	}

	rdb := redis.NewClient(&redis.Options{
		Addr: config.RedisURL,
	})

	userService := NewUserService(db, rdb)
	userHandler := NewUserHandler(userService)

	router := setupRouter(userHandler)

	workerPool := NewWorkerPool(5)
	workerPool.Start()
	defer workerPool.Stop()

	addr := ":" + config.Port
	log.Printf("Server starting on %s", addr)

	srv := &http.Server{
		Addr:    addr,
		Handler: router,
	}

	if err := srv.ListenAndServe(); err != nil {
		log.Fatal("Server failed to start:", err)
	}
}