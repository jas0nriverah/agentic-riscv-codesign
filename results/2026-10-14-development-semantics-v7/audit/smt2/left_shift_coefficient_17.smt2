(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x198 (bvmul x (_ bv131072 32))))
(let ((?x196 (bvshl x (_ bv17 32))))
(and (distinct ?x196 ?x198) true))))
(check-sat)
