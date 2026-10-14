(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x225 (bvmul x (_ bv1048576 32))))
(let ((?x223 (bvshl x (_ bv20 32))))
(and (distinct ?x223 ?x225) true))))
(check-sat)
