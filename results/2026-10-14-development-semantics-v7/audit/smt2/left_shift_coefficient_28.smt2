(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x297 (bvmul x (_ bv268435456 32))))
(let ((?x295 (bvshl x (_ bv28 32))))
(and (distinct ?x295 ?x297) true))))
(check-sat)
