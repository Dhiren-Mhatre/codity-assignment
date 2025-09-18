package com.example.service;

import java.util.List;
import java.util.ArrayList;
import java.util.Map;
import java.util.HashMap;
import java.util.Optional;
import java.util.stream.Collectors;
import javax.persistence.Entity;
import javax.persistence.Id;
import org.springframework.stereotype.Service;
import org.springframework.data.jpa.repository.JpaRepository;

 
@Service
public class UserService {

    private final UserRepository userRepository;
    private final EmailValidator emailValidator;

    public UserService(UserRepository userRepository, EmailValidator emailValidator) {
        this.userRepository = userRepository;
        this.emailValidator = emailValidator;
    }

    public List<User> findAllUsers() {
        return userRepository.findAll();
    }

    public Optional<User> findUserById(Long id) {
        return userRepository.findById(id);
    }

    public User createUser(String name, String email) {
        if (!emailValidator.isValid(email)) {
            throw new IllegalArgumentException("Invalid email address");
        }

        User user = new User();
        user.setName(name);
        user.setEmail(email);
        user.setCreatedAt(new Date());

        return userRepository.save(user);
    }

    public void deleteUser(Long id) {
        userRepository.deleteById(id);
    }

    public List<User> findUsersByEmailDomain(String domain) {
        return findAllUsers()
            .stream()
            .filter(user -> user.getEmail().endsWith("@" + domain))
            .collect(Collectors.toList());
    }

    private boolean isValidUser(User user) {
        return user != null &&
               user.getName() != null &&
               !user.getName().trim().isEmpty() &&
               emailValidator.isValid(user.getEmail());
    }

    public Map<String, Integer> getUserStatistics() {
        List<User> users = findAllUsers();
        Map<String, Integer> stats = new HashMap<>();

        stats.put("totalUsers", users.size());
        stats.put("validUsers", (int) users.stream().filter(this::isValidUser).count());

        return stats;
    }

    static class EmailValidator {
        public boolean isValid(String email) {
            return email != null && email.contains("@") && email.contains(".");
        }
    }

    @Entity
    static class User {
        @Id
        private Long id;
        private String name;
        private String email;
        private Date createdAt;

     
        public Long getId() { return id; }
        public void setId(Long id) { this.id = id; }

        public String getName() { return name; }
        public void setName(String name) { this.name = name; }

        public String getEmail() { return email; }
        public void setEmail(String email) { this.email = email; }

        public Date getCreatedAt() { return createdAt; }
        public void setCreatedAt(Date createdAt) { this.createdAt = createdAt; }
    }

    interface UserRepository extends JpaRepository<User, Long> {
        List<User> findByEmailContaining(String emailPart);
    }

    public static void main(String[] args) {
        System.out.println("Java UserService test");
    }
}