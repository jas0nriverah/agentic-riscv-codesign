(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x136 (bvmul x (_ bv1024 32))))
(let ((?x134 (bvshl x (_ bv10 32))))
(and (distinct ?x134 ?x136) true))))
(check-sat)
