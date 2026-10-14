(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x154 (bvmul x (_ bv4096 32))))
(let ((?x152 (bvshl x (_ bv12 32))))
(and (distinct ?x152 ?x154) true))))
(check-sat)
