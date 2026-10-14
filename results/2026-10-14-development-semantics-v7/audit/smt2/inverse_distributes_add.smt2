(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x25 (bvneg y)))
(let ((?x29 (bvadd (bvneg x) ?x25)))
(let ((?x19 (bvadd x y)))
(let ((?x27 (bvneg ?x19)))
(and (distinct ?x27 ?x29) true))))))
(check-sat)
