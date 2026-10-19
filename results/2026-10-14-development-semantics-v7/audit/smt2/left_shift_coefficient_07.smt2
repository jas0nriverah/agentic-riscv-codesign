(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x110 (bvmul x (_ bv128 32))))
(let ((?x108 (bvshl x (_ bv7 32))))
(and (distinct ?x108 ?x110) true))))
(check-sat)
